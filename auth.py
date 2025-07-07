import os
from typing import Dict

from dotenv import load_dotenv
from fasthtml.oauth import GoogleAppClient, OAuth
from starlette.responses import RedirectResponse


load_dotenv()

SUPERADMIN = os.getenv("SUPERADMIN")


cli = GoogleAppClient(
    os.getenv("GOOGLE_CLIENT_ID"),
    os.getenv("GOOGLE_CLIENT_SECRET"),
)


class Auth(OAuth):
    def get_auth(self, info: Dict, ident, session: Dict, state) -> RedirectResponse:
        """
        Handles the authentication callback, stores user info in the session, and redirects to the index page.

        Args:
            info (dict): Dictionary containing token information from the OAuth provider.
            ident: Identifier related to the OAuth flow.
            session (dict): The user's session dictionary.
            state: State parameter used during the OAuth flow.

        Returns:
            RedirectResponse: A redirect response for authenticated users.
        """
        # Store both the ident and the token info in session
        session["token"] = info.get("access_token")
        session["user_info"] = info
        user_email = info.get("email", "")

        if user_email == SUPERADMIN:
            session["user_group"] = "super_admin"
        else:
            session["user_group"] = "guest"

        return RedirectResponse("/", status_code=303)
