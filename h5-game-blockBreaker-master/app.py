from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///steam_game.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.static_folder = 'static'
app.static_url_path = '/static'

# 初始化数据库
db = SQLAlchemy(app)

# 添加全局上下文处理器，提供now变量给所有模板
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

# 添加全局上下文处理器，提供语言变量给所有模板
@app.context_processor
def inject_language():
    # 默认语言为中文
    return {'language': session.get('language', 'zh')}

# 用户模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    avatar = db.Column(db.String(200), default='default_avatar.jpg')
    bio = db.Column(db.Text, default='这个用户很懒，还没有填写个人简介。')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    comments = db.relationship('Comment', backref='author', lazy=True)
    posts = db.relationship('Post', backref='author', lazy=True)
    replies = db.relationship('Reply', backref='author', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# 评论模型
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)  # 1-5星评分
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.Integer, default=1)  # 默认为打砖块游戏ID

# 帖子模型
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    replies = db.relationship('Reply', backref='post', lazy=True, cascade="all, delete-orphan")
    
    # 新增字段
    view_count = db.Column(db.Integer, default=0)  # 浏览次数
    like_count = db.Column(db.Integer, default=0)  # 点赞数
    category = db.Column(db.String(50), default='讨论')  # 帖子分类
    is_pinned = db.Column(db.Boolean, default=False)  # 是否置顶
    is_featured = db.Column(db.Boolean, default=False)  # 是否精华帖
    cover_image = db.Column(db.String(200))  # 封面图片
    tags = db.Column(db.String(200))  # 标签，以逗号分隔
    
    def __repr__(self):
        return f'<Post {self.title}>'

# 回复模型
class Reply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    
    def __repr__(self):
        return f'<Reply {self.id}>'

# 创建数据库表
with app.app_context():
    db.create_all()

# 首页路由
@app.route('/')
def index():
    return render_template('steam-style.html')

# 注册路由
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('用户名已存在')
            return redirect(url_for('register'))
            
        if User.query.filter_by(email=email).first():
            flash('邮箱已被注册')
            return redirect(url_for('register'))
            
        user = User(username=username, email=email)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('注册成功！请登录')
        return redirect(url_for('login'))
        
    return render_template('register.html')

# 登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            
            # 检查是否是AJAX请求
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': '登录成功'})
            else:
                flash('登录成功')
                return redirect(url_for('index'))
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': '用户名或密码错误'})
            else:
                flash('用户名或密码错误')
                return render_template('login.html')
    
    return render_template('login.html')

# 登出路由
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('您已成功登出')
    return redirect(url_for('index'))

# 个人资料路由
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('请先登录')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    return render_template('profile.html', user=user)

# 编辑个人资料路由
@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        flash('请先登录')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        email = request.form.get('email')
        bio = request.form.get('bio')
        
        # 检查邮箱是否已被其他用户使用
        existing_email = User.query.filter_by(email=email).first()
        if existing_email and existing_email.id != user.id:
            flash('邮箱已被其他用户注册')
            return redirect(url_for('edit_profile'))
        
        user.email = email
        user.bio = bio
        
        # 处理头像上传
        if 'avatar' in request.files:
            avatar_file = request.files['avatar']
            if avatar_file.filename != '':
                # 保存头像文件
                avatar_filename = f"user_{user.id}_{avatar_file.filename}"
                avatar_path = os.path.join('static/uploads', avatar_filename)
                avatar_file.save(avatar_path)
                user.avatar = f"uploads/{avatar_filename}"
        
        db.session.commit()
        flash('个人资料已更新')
        return redirect(url_for('profile'))
    
    return render_template('edit_profile.html', user=user)

# 添加评论路由
@app.route('/add_comment', methods=['POST'])
def add_comment():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
    content = request.form.get('content')
    rating = request.form.get('rating')
    
    if not content or not rating:
        return jsonify({'success': False, 'message': '请填写完整的评论信息'})
    
    try:
        comment = Comment(
            content=content,
            rating=int(rating),
            user_id=session['user_id']
        )
        db.session.add(comment)
        db.session.commit()
        return jsonify({'success': True, 'message': '评论发布成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': '评论发布失败，请稍后重试'})

# API获取评论
@app.route('/get_comments')
def get_comments():
    comments = Comment.query.order_by(Comment.created_at.desc()).all()
    return jsonify([{
        'id': comment.id,
        'content': comment.content,
        'rating': comment.rating,
        'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'username': comment.author.username,
        'avatar': url_for('static', filename=comment.author.avatar if comment.author.avatar.startswith('uploads/') else 'images/' + comment.author.avatar)
    } for comment in comments])

# 游戏路由
@app.route('/game')
def game():
    return send_from_directory('static', 'index.html')

# 语言设置路由
@app.route('/set_language/<language>')
def set_language(language):
    # 保存语言设置到session
    session['language'] = language
    # 重定向回之前的页面
    return redirect(request.referrer or url_for('index'))

# 社区首页
@app.route('/community')
def community():
    # 获取分类参数
    category = request.args.get('category', '全部')
    
    # 获取置顶帖子
    pinned_posts = Post.query.filter_by(is_pinned=True).order_by(Post.created_at.desc()).all()
    
    # 根据分类筛选帖子
    if category != '全部':
        regular_posts = Post.query.filter_by(category=category, is_pinned=False).order_by(Post.created_at.desc()).all()
    else:
        regular_posts = Post.query.filter_by(is_pinned=False).order_by(Post.created_at.desc()).all()
    
    # 获取热门标签
    all_tags = []
    for post in Post.query.all():
        if post.tags:
            all_tags.extend(post.tags.split(','))
    tag_counts = {}
    for tag in all_tags:
        tag = tag.strip()
        if tag:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    popular_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # 获取活跃用户
    active_users = User.query.join(Post).group_by(User.id).order_by(db.func.count(Post.id).desc()).limit(5).all()
    
    return render_template('community.html', 
                          pinned_posts=pinned_posts, 
                          regular_posts=regular_posts, 
                          popular_tags=popular_tags,
                          active_users=active_users,
                          current_category=category)

# 查看帖子详情
@app.route('/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    replies = Reply.query.filter_by(post_id=post_id).order_by(Reply.created_at).all()
    
    # 增加帖子浏览次数统计
    post.view_count = post.view_count + 1 if hasattr(post, 'view_count') else 1
    db.session.commit()
    
    # 获取相关帖子推荐
    related_posts = Post.query.filter(Post.id != post_id).order_by(Post.created_at.desc()).limit(5).all()
    
    return render_template('post.html', post=post, replies=replies, related_posts=related_posts)

# 创建新帖子
@app.route('/create_post', methods=['GET', 'POST'])
def create_post():
    if 'user_id' not in session:
        flash('请先登录')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category', '讨论')
        tags = request.form.get('tags', '')
        
        if not title or not content:
            flash('标题和内容不能为空')
            return redirect(url_for('create_post'))
            
        post = Post(
            title=title,
            content=content,
            user_id=session['user_id'],
            category=category,
            tags=tags
        )
        
        # 处理封面图片上传
        if 'cover_image' in request.files:
            cover_file = request.files['cover_image']
            if cover_file.filename != '':
                # 保存封面图片
                cover_filename = f"post_{datetime.now().strftime('%Y%m%d%H%M%S')}_{cover_file.filename}"
                cover_path = os.path.join('static/uploads/covers', cover_filename)
                os.makedirs(os.path.dirname(cover_path), exist_ok=True)
                cover_file.save(cover_path)
                post.cover_image = f"uploads/covers/{cover_filename}"
        
        db.session.add(post)
        db.session.commit()
        
        flash('帖子发布成功')
        return redirect(url_for('view_post', post_id=post.id))
    
    # 获取所有可用分类    
    categories = ['讨论', '攻略', '问答', '分享', '建议', '打砖块', '植物大战僵尸', '其他']
    
    # 强制刷新模板
    return render_template('create_post.html', categories=categories, cache_id=datetime.now().timestamp())

# 添加回复
@app.route('/post/<int:post_id>/reply', methods=['POST'])
def add_reply(post_id):
    if 'user_id' not in session:
        flash('请先登录')
        return redirect(url_for('login'))
        
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content')
    
    if not content:
        flash('回复内容不能为空')
        return redirect(url_for('view_post', post_id=post_id))
        
    reply = Reply(
        content=content,
        user_id=session['user_id'],
        post_id=post_id
    )
    
    db.session.add(reply)
    db.session.commit()
    
    flash('回复成功')
    return redirect(url_for('view_post', post_id=post_id))

# 点赞帖子
@app.route('/post/<int:post_id>/like', methods=['POST'])
def like_post(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
    post = Post.query.get_or_404(post_id)
    post.like_count += 1
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': '点赞成功', 
        'like_count': post.like_count
    })

# 收藏帖子
@app.route('/post/<int:post_id>/favorite', methods=['POST'])
def favorite_post(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
    # 这里需要添加一个收藏表模型，此处简化处理
    return jsonify({
        'success': True, 
        'message': '收藏成功'
    })

# 搜索帖子
@app.route('/search')
def search_posts():
    query = request.args.get('q', '')
    if not query:
        return redirect(url_for('community'))
    
    # 搜索标题和内容
    posts = Post.query.filter(
        db.or_(
            Post.title.contains(query),
            Post.content.contains(query),
            Post.tags.contains(query)
        )
    ).order_by(Post.created_at.desc()).all()
    
    return render_template('search_results.html', posts=posts, query=query)

# 在现有代码中添加以下函数，用于重建数据库表

@app.route('/rebuild_db')
def rebuild_db():
    # 此路由仅用于开发环境，生产环境应移除或添加权限控制
    with app.app_context():
        # 备份现有数据（可选）
        posts = Post.query.all()
        post_data = []
        for post in posts:
            post_data.append({
                'title': post.title,
                'content': post.content,
                'user_id': post.user_id,
                'created_at': post.created_at
            })
            
        # 删除并重建表
        db.drop_all()
        db.create_all()
        
        # 恢复数据（可选）
        for data in post_data:
            new_post = Post(
                title=data['title'],
                content=data['content'],
                user_id=data['user_id'],
                created_at=data['created_at']
            )
            db.session.add(new_post)
            
        db.session.commit()
        return '数据库已重建'

@app.route('/test_post', methods=['GET', 'POST'])
def test_post():
    if request.method == 'POST':
        flash('测试提交成功')
        return redirect(url_for('test_post'))
    return render_template('create_post_simple.html')

# 植物大战僵尸游戏路由
@app.route('/plants_vs_zombies')
def plants_vs_zombies():
    return render_template('plants_vs_zombies.html')

# 游戏数据
games = [
    {
        'id': 'block_breaker',
        'name_en': 'Block Breaker',
        'name_zh': '打砖块',
        'description_en': 'Break all the blocks to win!',
        'description_zh': '打破所有砖块获得胜利！',
        'tags_en': ['Arcade', 'Classic'],
        'tags_zh': ['街机', '经典'],
        'route': 'game',
        'cover': 'images/block_breaker_cover.jpg'
    },
    {
        'id': 'plants_vs_zombies',
        'name_en': 'Plants vs Zombies',
        'name_zh': '植物大战僵尸',
        'description_en': 'Defend your garden from zombies with an army of plants!',
        'description_zh': '用植物军团保卫你的花园，抵御僵尸入侵！',
        'tags_en': ['Strategy', 'Tower Defense'],
        'tags_zh': ['策略', '塔防'],
        'route': 'plants_vs_zombies',
        'cover': 'images/plants_vs_zombies_cover.jpg'
    }
]

# 游戏列表路由
@app.route('/games')
def games_list():
    return render_template('games.html', games=games)

# 动态游戏路由
@app.route('/play/<game_id>')
def play_game(game_id):
    for game in games:
        if game['id'] == game_id:
            return redirect(url_for(game['route']))
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)