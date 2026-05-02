        result = []
    for t in tickets:
        user = db.query(User).filter(User.id == t.user_id).first() if t.user_id else None
        result.append({
            "id": t.id,
            "description": t.description,
            "category": t.category,
            "division": t.division,
            "user_email": t.user_email,
            "user_name": user.full_name if user else None,
            "status": t.status,
            "admin_response": t.admin_response,
            "image_url": t.image_url,
            "created_at": t.created_at
        })
    
    return result