from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, FileField
from wtforms.validators import DataRequired, Length
from flask_socketio import emit, join_room, leave_room
import os
from datetime import datetime
from werkzeug.utils import secure_filename

from app import db, socketio
from models import ChatRoom, ChatRoomMember, ChatMessage, Message, User, AuditLog, UserRole

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

# Forms
class DirectMessageForm(FlaskForm):
    content = TextAreaField('Message', validators=[DataRequired()])
    file = FileField('Attach File')
    submit = SubmitField('Send')

class ChatRoomForm(FlaskForm):
    name = StringField('Room Name', validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    submit = SubmitField('Create Room')

class ChatMessageForm(FlaskForm):
    content = TextAreaField('Message', validators=[DataRequired()])
    file = FileField('Attach File')
    submit = SubmitField('Send')

# Helper function for file uploads
def save_chat_file(file):
    if not file:
        return None
    
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    new_filename = f"{timestamp}_{filename}"
    
    upload_path = os.path.join('uploads', 'chat_files')
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)
    
    file_path = os.path.join(upload_path, new_filename)
    file.save(file_path)
    
    return os.path.join('chat_files', new_filename)

# Routes
@chat_bp.route('/')
@login_required
def index():
    # Get rooms that the user is a member of
    user_rooms = ChatRoom.query.join(ChatRoomMember).filter(
        ChatRoomMember.user_id == current_user.id
    ).all()
    
    # Get public rooms that the user is not a member of
    public_rooms = ChatRoom.query.filter(
        ChatRoom.is_private == False,
        ~ChatRoom.id.in_([room.id for room in user_rooms])
    ).all()
    
    # Combine user rooms and public rooms
    chat_rooms = user_rooms + public_rooms
    
    # Get users for direct messaging
    users = User.query.filter(
        User.id != current_user.id,
        User.is_active == True
    ).order_by(User.username).all()
    
    # Get direct messages
    direct_messages = []
    for user in users:
        unread_count = Message.query.filter_by(
            sender_id=user.id,
            recipient_id=current_user.id,
            is_read=False
        ).count()
        
        direct_messages.append({
            'user': user,
            'unread_count': unread_count
        })
    
    return render_template(
        'chat/index.html',
        chat_rooms=chat_rooms,
        direct_messages=direct_messages,
        users=users,
        room_form=ChatRoomForm(),
        form=ChatMessageForm()
    )

@chat_bp.route('/room/<int:room_id>')
@login_required
def room(room_id):
    room = ChatRoom.query.get_or_404(room_id)
    
    # Check if user is a member of the room
    is_member = ChatRoomMember.query.filter_by(
        chat_room_id=room.id,
        user_id=current_user.id
    ).first() is not None
    
    # Check if the room is private and user is not a member
    if room.is_private and not is_member:
        flash('You do not have permission to view this chat room.', 'danger')
        return redirect(url_for('chat.index'))
    
    # Join the room if not already a member
    if not is_member:
        member = ChatRoomMember(
            chat_room_id=room.id,
            user_id=current_user.id
        )
        db.session.add(member)
        db.session.commit()
    
    # Get room messages
    messages = ChatMessage.query.filter_by(
        chat_room_id=room.id
    ).order_by(ChatMessage.created_at).all()
    
    # Get room members
    members = User.query.join(ChatRoomMember).filter(
        ChatRoomMember.chat_room_id == room.id
    ).all()
    
    return render_template(
        'chat/room.html',
        room=room,
        messages=messages,
        members=members,
        form=ChatMessageForm()
    )

@chat_bp.route('/direct/<int:user_id>', methods=['GET', 'POST'])
@login_required
def direct_message(user_id):
    recipient = User.query.get_or_404(user_id)
    
    # Ensure user is not messaging themselves
    if recipient.id == current_user.id:
        flash('You cannot send a direct message to yourself.', 'warning')
        return redirect(url_for('chat.index'))
    
    form = DirectMessageForm()
    
    if form.validate_on_submit():
        content = form.content.data
        
        # Handle file upload
        file_path = None
        if form.file.data:
            file_path = save_chat_file(form.file.data)
        
        # Create message
        message = Message(
            sender_id=current_user.id,
            recipient_id=recipient.id,
            content=content,
            file_path=file_path
        )
        db.session.add(message)
        db.session.commit()
        
        # Emit message via WebSocket
        socketio.emit('direct_message', {
            'sender_id': current_user.id,
            'recipient_id': recipient.id,
            'sender_name': f"{current_user.first_name} {current_user.last_name}",
            'content': content,
            'file_path': file_path,
            'timestamp': message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }, room=f"user_{recipient.id}")
        
        flash('Message sent.', 'success')
        return redirect(url_for('chat.direct_message', user_id=recipient.id))
    
    # Mark messages as read
    unread_messages = Message.query.filter_by(
        sender_id=recipient.id,
        recipient_id=current_user.id,
        is_read=False
    ).all()
    
    for msg in unread_messages:
        msg.is_read = True
    
    db.session.commit()
    
    # Get conversation history
    sent_messages = Message.query.filter_by(
        sender_id=current_user.id,
        recipient_id=recipient.id
    ).all()
    
    received_messages = Message.query.filter_by(
        sender_id=recipient.id,
        recipient_id=current_user.id
    ).all()
    
    messages = sorted(sent_messages + received_messages, key=lambda x: x.created_at)
    
    return render_template(
        'chat/direct_message.html',
        recipient=recipient,
        messages=messages,
        form=form
    )

@chat_bp.route('/room/create', methods=['POST'])
@login_required
def create_room():
    form = ChatRoomForm()
    
    if form.validate_on_submit():
        # Check if user has permission to create rooms
        if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            # TODO: Add a check for user authorization to create rooms
            # For now, all authenticated users can create rooms
            pass
        
        room = ChatRoom(
            name=form.name.data,
            description=form.description.data,
            is_private=False,  # Default to public room for regular users
            created_by=current_user.id
        )
        
        db.session.add(room)
        db.session.commit()
        
        # Add creator as a room member and admin
        member = ChatRoomMember(
            chat_room_id=room.id,
            user_id=current_user.id,
            is_admin=True
        )
        db.session.add(member)
        
        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="Created chat room",
            resource_type="ChatRoom",
            resource_id=room.id,
            details=f"Room name: {room.name}",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        flash(f'Chat room "{room.name}" created successfully.', 'success')
        return redirect(url_for('chat.room', room_id=room.id))
    
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'{getattr(form, field).label.text}: {error}', 'danger')
    
    return redirect(url_for('chat.index'))

@chat_bp.route('/room/<int:room_id>/leave', methods=['POST'])
@login_required
def leave_chat_room(room_id):
    member = ChatRoomMember.query.filter_by(
        chat_room_id=room_id,
        user_id=current_user.id
    ).first_or_404()
    
    room_name = member.chat_room.name
    
    db.session.delete(member)
    db.session.commit()
    
    flash(f'You have left the chat room "{room_name}".', 'info')
    return redirect(url_for('chat.index'))

@chat_bp.route('/room/<int:room_id>/message', methods=['POST'])
@login_required
def send_room_message(room_id):
    room = ChatRoom.query.get_or_404(room_id)
    
    # Check if user is a member of the room
    is_member = ChatRoomMember.query.filter_by(
        chat_room_id=room.id,
        user_id=current_user.id
    ).first() is not None
    
    if not is_member:
        flash('You are not a member of this chat room.', 'danger')
        return redirect(url_for('chat.index'))
    
    form = ChatMessageForm()
    
    if form.validate_on_submit():
        content = form.content.data
        
        # Handle file upload
        file_path = None
        if form.file.data:
            file_path = save_chat_file(form.file.data)
        
        # Create message
        message = ChatMessage(
            chat_room_id=room.id,
            user_id=current_user.id,
            content=content,
            file_path=file_path
        )
        db.session.add(message)
        db.session.commit()
        
        # Emit message via WebSocket
        socketio.emit('room_message', {
            'room_id': room.id,
            'user_id': current_user.id,
            'user_name': f"{current_user.first_name} {current_user.last_name}",
            'content': content,
            'file_path': file_path,
            'timestamp': message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }, room=f"room_{room.id}")
    
    return redirect(url_for('chat.room', room_id=room.id))

# WebSocket events
@socketio.on('join')
def on_join(data):
    room = data.get('room')
    if room:
        join_room(room)
        emit('status', {
            'msg': f"{current_user.first_name} {current_user.last_name} has joined the room.",
            'user_id': current_user.id,
            'user_name': f"{current_user.first_name} {current_user.last_name}"
        }, room=room)

@socketio.on('leave')
def on_leave(data):
    room = data.get('room')
    if room:
        leave_room(room)
        emit('status', {
            'msg': f"{current_user.first_name} {current_user.last_name} has left the room.",
            'user_id': current_user.id,
            'user_name': f"{current_user.first_name} {current_user.last_name}"
        }, room=room)

@socketio.on('message')
def handle_message(data):
    room = data.get('room')
    content = data.get('content')
    file_path = data.get('file_path')
    
    if room and content:
        # Create message in database
        message = ChatMessage(
            chat_room_id=room,
            user_id=current_user.id,
            content=content,
            file_path=file_path
        )
        db.session.add(message)
        db.session.commit()
        
        # Emit message to room
        emit('message', {
            'user_id': current_user.id,
            'user_name': f"{current_user.first_name} {current_user.last_name}",
            'content': content,
            'file_path': file_path,
            'timestamp': message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }, room=room)
