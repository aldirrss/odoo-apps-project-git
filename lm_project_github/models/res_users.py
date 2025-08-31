from odoo import fields, models, api
import hashlib
import requests
from requests.auth import HTTPBasicAuth
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = 'res.users'

    git_username = fields.Char(
        string='Github Username',
        readonly=True,
        help='Github Username for authentication',
    )
    git_token = fields.Char(
        string='Github Token',
        readonly=True,
        help='Personal Access Token for Github integration',
    )
    is_connected = fields.Boolean(
        string='Connected to Github',
    )

    def action_config_git_connection(self):
        self.ensure_one()
        return {
            'name': 'Git Credentials',
            'type': 'ir.actions.act_window',
            'res_model': 'res.users.git.credential',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_id': self.id,
                'default_git_username': self.git_username,
            },
        }

    def action_test_git_connection(self):
        self.ensure_one()
        if not self.git_username or not self.git_token:
            raise UserError("GitHub credentials are not set.")

        # Here you would implement the actual connection test to GitHub
        # For demonstration, we'll just simulate a successful connection
        # In a real scenario, you might use requests or a GitHub API client

        # Simulated connection test
        try:
            # Simulate API call to GitHub
            response = requests.get(
                'https://api.github.com/user',
                auth=HTTPBasicAuth(self.git_username, self.git_token),
                timeout=10
            )
            if response.status_code == 200:
                self.write({'is_connected': True})
                msg = f"Connected as {response.json().get('login')}"
                msg_type = "success"
            else:
                self.write({'is_connected': False})
                msg = f"Connection failed: {response.json().get('message')}"
                msg_type = "danger"
                print('GitHub connection test failed with status code:', response.status_code)
        except Exception as e:
            self.write({'is_connected': False})
            raise UserError(f"Failed to connect to GitHub: {str(e)}")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "GitHub Connection Test",
                "message": msg,
                "type": msg_type,
                "sticky": False,
            },
        }

    def action_clear_git_connection(self):
        self.ensure_one()
        self.git_username = False
        self.git_token = False
        self.is_connected = False
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }