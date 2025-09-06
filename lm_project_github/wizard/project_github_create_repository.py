import requests
from odoo import fields, models, _
from odoo.exceptions import UserError


class ProjectGithubCreateRepository(models.Model):
    _name = "project.github.create.repository"
    _description = "Create GitHub Repository Wizard"

    name = fields.Char(string="Repository Name", required=True)
    description = fields.Text(string="Description")
    commit_prefix = fields.Char(string="Commit Prefix", size=5)
    private = fields.Boolean(string="Private", default=False)

    def _header_authentication(self):
        token = self.env.user.git_token
        return {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
        }

    def action_post_repository(self):
        self.ensure_one()
        if not self.name:
            raise UserError(_("Repository name is not set."))

        token = self.env.user.git_token
        base_url = self.env.company.github_instance_url or 'https://api.github.com'

        if not token:
            raise UserError(_("GitHub token is not set for the user."))

        payload = {
            "name": self.name,
            "description": self.description or "",
            "private": self.private,
        }

        repos = self.env['project.github.repository']
        if repos.search([("name", "=", self.name)]):
            raise UserError('Repository with this name already exists in Odoo.')

        try:
            response = requests.post(
                f"{base_url}/user/repos",
                headers=self._header_authentication(),
                json=payload,
                timeout=10
            )
            if response.status_code == 201:
                repo_data = response.json()
                avatar_url = repo_data.get('owner', {}).get('avatar_url', '')
                image = base64.b64encode(requests.get(avatar_url.strip()).content).replace(b"\n", b"")
                repos.create({
                    'name': repo_data.get('name', []),
                    'description': repo_data.get('description', ''),
                    'commit_prefix': self.commit_prefix or '',
                    'github_id': str(repo_data.get('id', '')),
                    'date_connected': datetime.now(),
                    'url': repo_data.get('html_url', ''),
                    'avatar_url': repo_data.get('owner', {}).get('avatar_url', ''),
                    'images': image if avatar_url else False,
                    'is_connected': True,
                    'owner': repo_data.get('owner', {}).get('login', ''),
                })
                return {
                    'name': _('GitHub Repository'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'project.github.repository',
                    'view_mode': 'form',
                    'res_id': repos.id,
                    'target': 'current',
                }
            else:
                raise UserError(_("Failed to create the repository. Please check your credentials and try again."))
        except requests.RequestException as e:
            raise UserError(_("An error occurred while creating the GitHub repository: %s") % str(e))
