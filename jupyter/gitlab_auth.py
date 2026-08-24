"""
gitlab_auth.py - GitLab OAuth 2.0 Single Sign-On & RTC Live Identity Synchronizer
Connects JupyterLab authentication to GitLab CE and sets live user identity (avatar, color, initials).
"""

import os
from jupyter_server.auth import IdentityProvider, User

class GitLabIdentityProvider(IdentityProvider):
    def get_user(self, handler):
        # Fallback or OAuth user resolution
        username = handler.get_secure_cookie("gitlab_user")
        if username:
            uname = username.decode("utf-8")
            return User(
                username=uname,
                name=uname.capitalize(),
                display_name=uname.capitalize(),
                initials=uname[:2].upper(),
                color=f"#{hash(uname) & 0xFFFFFF:06x}"
            )
        return super().get_user(handler)
