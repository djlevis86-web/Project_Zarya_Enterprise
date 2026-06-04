def is_admin(user):
    return user.role == 'ADMIN'


def is_manager(user):
    return user.role == 'MANAGER'


def is_analyst(user):
    return user.role == 'ANALYST'