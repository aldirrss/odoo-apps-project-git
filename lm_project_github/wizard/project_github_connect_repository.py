from odoo import fields, models, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class ProjectGithubConnectRepositoryList(models.TransientModel):
    _name = "project.github.connect.repository.list"
    _description = "Connect GitHub Repository List"

    name = fields.Char(string="Repository Name", required=True)
    connect_repository_id = fields.Many2one(
        comodel_name="project.github.connect.repository",
        string="Connect Repository",
        ondelete="cascade",
    )
    repository_id = fields.Char(string="ID", readonly=True)
    owner = fields.Char(string="Owner", required=True)
    description = fields.Text(string="Description", readonly=True)
    private = fields.Boolean(string="Private", readonly=True)
    full_name = fields.Char(string="Full Name", readonly=True)
    html_url = fields.Char(string="URL", readonly=True)
    clone_url = fields.Char(string="Clone URL", readonly=True)
    ssh_url = fields.Char(string="SSH URL", readonly=True)
    default_branch = fields.Char(string="Default Branch", readonly=True)
    language = fields.Char(string="Primary Language", readonly=True)
    stars_count = fields.Integer(string="Stars", readonly=True)
    forks_count = fields.Integer(string="Forks", readonly=True)
    open_issues_count = fields.Integer(string="Open Issues", readonly=True)
    archive = fields.Boolean(string="Archived", readonly=True)
    disabled = fields.Boolean(string="Disabled", readonly=True)
    visibility = fields.Char(string="Visibility", readonly=True)
    created_at = fields.Datetime(string="Created At", readonly=True)
    updated_at = fields.Datetime(string="Updated At", readonly=True)

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.owner}/{record.name}"
            if record.private:
                name += " (Private)"
            result.append((record.id, name))
        return result

    def action_select_repository(self):
        """Action to select this repository"""
        self.ensure_one()
        wizard = self.connect_repository_id
        if not wizard:
            raise UserError(_('Wizard context is missing.'))

        wizard.selected_repository_id = self
        wizard.selected_repository_name = self.full_name

        return {
            'name': _("Connect GitHub Repository: %s") % wizard.project_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'project.github.connect.repository',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
            'context': self.env.context,
        }


class ProjectGithubConnectRepository(models.TransientModel):
    _name = "project.github.connect.repository"
    _description = "Connect GitHub Repository"

    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Project",
        required=True,
        ondelete="cascade",
        readonly=True,
    )
    github_username = fields.Char(
        string="GitHub Username",
        help="Leave empty to fetch your own repositories"
    )
    date_connected = fields.Datetime(
        string="Date Connected",
        default=fields.Datetime.now,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
    )

    # State management
    state = fields.Selection([
        ('form', 'Form Validation'),
        ('select_repo', 'Select Repository'),
        ('preview', 'Preview Data'),
    ], string='State', default='form')

    # Repository list for selection
    repository_ids = fields.One2many(
        comodel_name="project.github.connect.repository.list",
        inverse_name="connect_repository_id",
        string="Repositories",
    )
    selected_repository_id = fields.Many2one(
        comodel_name="project.github.connect.repository.list",
        string="Selected Repository",
        domain="[('connect_repository_id', '=', id)]",
    )
    selected_repository_name = fields.Char(
        string="Selected Repository Name",
        readonly=True
    )

    # Repository type filter
    repo_type = fields.Selection([
        ('all', 'All Repositories'),
        ('owner', 'Owner Repositories'),
        ('public', 'Public Repositories'),
        ('private', 'Private Repositories'),
        ('member', 'Member Repositories'),
    ], string='Repository Type', default='all')

    # Sorting options
    sort_by = fields.Selection([
        ('created', 'Created Date'),
        ('updated', 'Updated Date'),
        ('pushed', 'Last Push'),
        ('full_name', 'Name'),
    ], string='Sort By', default='updated')

    sort_direction = fields.Selection([
        ('asc', 'Ascending'),
        ('desc', 'Descending'),
    ], string='Sort Direction', default='desc')

    # Preview field
    preview_data = fields.Html(string="Preview Data", readonly=True)

    # Statistics
    total_repositories = fields.Integer(string="Total Repositories", readonly=True)
    public_count = fields.Integer(string="Public Repositories", readonly=True)
    private_count = fields.Integer(string="Private Repositories", readonly=True)

    def _header_authentication(self):
        """Get authentication headers for GitHub API"""
        token = self.env.user.git_token
        if not token:
            raise UserError(_('GitHub token is not configured. Please set up your GitHub token in user preferences.'))

        return {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
        }

    def _get_github_api_url(self):
        """Get the appropriate GitHub API URL based on username"""
        return "https://api.github.com/user/repos"

    def action_fetch_repositories(self):
        """Fetch repositories from GitHub"""
        self.ensure_one()

        try:
            headers = self._header_authentication()
        except UserError as e:
            raise e

        # Build API URL with parameters
        url = self._get_github_api_url()
        params = {
            'type': self.repo_type,
            'sort': self.sort_by,
            'direction': self.sort_direction,
            'per_page': 100,  # Maximum per page
        }

        all_repositories = []
        page = 1

        try:
            while True:
                params['page'] = page
                _logger.info(f"Fetching repositories from GitHub API: {url}, page {page}")

                response = requests.get(url, headers=headers, params=params, timeout=30)

                if response.status_code == 401:
                    raise UserError(_('GitHub authentication failed. Please check your token.'))
                elif response.status_code == 403:
                    raise UserError(_('GitHub API rate limit exceeded. Please try again later.'))
                elif response.status_code == 404:
                    raise UserError(_('Unable to access your repositories. Please check your token permissions.'))
                elif response.status_code != 200:
                    raise UserError(_('GitHub API error: %s') % response.text)

                repositories = response.json()

                if not repositories:  # No more repositories
                    break

                all_repositories.extend(repositories)
                page += 1

                # Safety check to prevent infinite loops
                if page > 10:  # Max 1000 repositories
                    break

        except requests.exceptions.RequestException as e:
            _logger.error(f"Error fetching GitHub repositories: {e}")
            raise UserError(_('Failed to connect to GitHub. Please check your internet connection.'))

        if not all_repositories:
            raise UserError(_('No repositories found for the specified criteria.'))

        # Clear existing repository records
        self.repository_ids.unlink()

        # Create repository records
        repo_vals = []
        public_count = 0
        private_count = 0

        for repo in all_repositories:
            try:
                # Parse created and updated dates
                created_at = None
                updated_at = None

                if repo.get('created_at'):
                    from datetime import datetime
                    created_at = datetime.strptime(repo['created_at'], '%Y-%m-%dT%H:%M:%SZ')

                if repo.get('updated_at'):
                    updated_at = datetime.strptime(repo['updated_at'], '%Y-%m-%dT%H:%M:%SZ')

                repo_data = {
                    'name': repo.get('name', ''),
                    'repository_id': str(repo.get('id', '')),
                    'owner': repo.get('owner', {}).get('login', ''),
                    'description': repo.get('description', ''),
                    'private': repo.get('private', False),
                    'full_name': repo.get('full_name', ''),
                    'html_url': repo.get('html_url', ''),
                    'clone_url': repo.get('clone_url', ''),
                    'ssh_url': repo.get('ssh_url', ''),
                    'default_branch': repo.get('default_branch', 'main'),
                    'language': repo.get('language', ''),
                    'open_issues_count': repo.get('open_issues_count', 0),
                    'stars_count': repo.get('stargazers_count', 0),
                    'forks_count': repo.get('forks_count', 0),
                    'archive': repo.get('archived', False),
                    'disabled': repo.get('disabled', False),
                    'visibility': repo.get('visibility', 'public'),
                    'created_at': created_at,
                    'updated_at': updated_at,
                }

                repo_vals.append((0, 0, repo_data))

                if repo.get('private'):
                    private_count += 1
                else:
                    public_count += 1

            except Exception as e:
                _logger.error(f"Error processing repository {repo.get('name', 'unknown')}: {e}")
                continue

        if not repo_vals:
            raise UserError(_('No valid repositories found to import.'))

        # Update wizard with repositories and statistics
        self.write({
            'repository_ids': repo_vals,
            'total_repositories': len(repo_vals),
            'public_count': public_count,
            'private_count': private_count,
            'state': 'select_repo'
        })

        _logger.info(f"Successfully fetched {len(repo_vals)} repositories from GitHub")

        return {
            'name': _("Connect GitHub Repository: %s") % self.project_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'project.github.connect.repository',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    def action_preview_repository(self):
        """Preview selected repository data"""
        self.ensure_one()

        if not self.selected_repository_id:
            raise UserError(_('Please select a repository to preview.'))

        repo = self.selected_repository_id

        # Generate preview HTML
        preview_html = '<div style="margin: 10px 0;">'

        # Repository Information
        # preview_html += '<h4>Repository Information:</h4>'
        preview_html += '<table style="width: 100%; border-collapse: collapse;">'

        info_items = [
            ('Name', repo.name),
            ('Full Name', repo.full_name),
            ('Owner', repo.owner),
            ('Description', repo.description or 'No description'),
            ('Private', 'Yes' if repo.private else 'No'),
            ('Primary Language', repo.language or 'Not specified'),
            ('Default Branch', repo.default_branch),
            ('Open Issues', str(repo.open_issues_count)),
            ('Stars', str(repo.stars_count)),
            ('Forks', str(repo.forks_count)),
            ('Archived', 'Yes' if repo.archive else 'No'),
            ('Disabled', 'Yes' if repo.disabled else 'No'),
            ('Visibility', repo.visibility.capitalize() if repo.visibility else 'Not specified'),
            ('Repository URL', f'<a href="{repo.html_url}" target="_blank">{repo.html_url}</a>'),
            ('Clone URL (HTTPS)', repo.clone_url),
            ('Clone URL (SSH)', repo.ssh_url),
        ]

        for label, value in info_items:
            preview_html += f'''
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold; background-color: #f5f5f5; width: 200px;">
                    {label}
                </td>
                <td style="padding: 8px; border: 1px solid #ddd;">
                    {value}
                </td>
            </tr>
            '''

        preview_html += '</table>'

        # Connection Details
        preview_html += '<h4 style="margin-top: 20px;">Connection Details:</h4>'
        preview_html += '<ul>'
        preview_html += f'<li><b>Project:</b> {self.project_id.name}</li>'
        preview_html += f'<li><b>Connected On:</b> {self.date_connected.strftime("%Y-%m-%d %H:%M:%S")}</li>'
        if repo.created_at:
            preview_html += f'<li><b>Repository Created:</b> {repo.created_at.strftime("%Y-%m-%d %H:%M:%S")}</li>'
        if repo.updated_at:
            preview_html += f'<li><b>Last Updated:</b> {repo.updated_at.strftime("%Y-%m-%d %H:%M:%S")}</li>'
        preview_html += '</ul>'

        # Warning for private repositories
        if repo.private:
            preview_html += '''
            <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; color: #856404; padding: 10px; margin: 10px 0; border-radius: 4px;">
                <b>⚠️ Private Repository:</b> Make sure you have proper access permissions for this private repository.
            </div>
            '''

        preview_html += '</div>'

        self.preview_data = preview_html
        self.state = 'preview'

        return {
            'name': _("Connect GitHub Repository: %s") % self.project_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'project.github.connect.repository',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    def action_back(self):
        """Go back to previous state"""
        self.ensure_one()

        if self.state == 'preview':
            self.state = 'select_repo'
        elif self.state == 'select_repo':
            self.state = 'form'

        return {
            'name': _("Connect GitHub Repository: %s") % self.project_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'project.github.connect.repository',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    def action_connect_repository(self):
        """Final action to connect the selected repository to the project"""
        self.ensure_one()

        if not self.selected_repository_id:
            raise UserError(_('Please select a repository to connect.'))

        repo = self.selected_repository_id

        # Check if repository is already connected to other projects
        existing_repos = self.env['project.github.repository'].search([
            ('repository_id', '=', repo.repository_id),
            ('full_name', '=', repo.full_name),
            ('name', '=', repo.name),
        ])

        if existing_repos:
            raise UserError(_(
                'Repository "%s" is already connected to project "%s".'
            ) % (repo.full_name, self.project_id.name))

        # Create the connection (adjust this based on your actual model structure)
        connection_vals = {
            'name': repo.name,
            'repository_id': repo.repository_id,
            'owner': repo.owner,
            'description': repo.description,
            'private': repo.private,
            'full_name': repo.full_name,
            'html_url': repo.html_url,
            'clone_url': repo.clone_url,
            'ssh_url': repo.ssh_url,
            'language': repo.language,
            'stars_count': repo.stars_count,
            'forks_count': repo.forks_count,
            'open_issues_count': repo.open_issues_count,
            'archive': repo.archive,
            'disabled': repo.disabled,
            'visibility': repo.visibility,
            'created_at': repo.created_at,
            'updated_at': repo.updated_at,
            'project_id': self.project_id.id,
            'company_id': self.company_id.id,
            'is_connected': True,
        }

        try:
            # Create the repository connection
            # Note: Adjust the model name based on your actual implementation
            repo_id = self.env['project.github.repository'].create(connection_vals)
            # create or update the default branch record
            branch_id = self._create_write_branches(
                project_id=self.project_id.id,
                default_branch=repo.default_branch,
                repo_id=repo_id.id
            )

            # write the project fields to indicate GitHub connection
            if repo_id:
                self.project_id.write({
                    'enable_github': True,
                    'repository_id': repo_id.id if repo_id else existing_repos,
                    'is_connected_github': True,
                    'github_url': repo.html_url,
                    'branch_ids': [(4, branch_id.id)]
                })

            # Update the repository with the default branch
            repo_id.write({'default_branch_id': branch_id.id})

            message = _(
                'Repository "%s" has been successfully connected to project "%s".'
            ) % (repo.full_name, self.project_id.name)

            # Log the connection in the project's chatter
            template_message = {
                'message': message,
                'action_link': repo.html_url,
                'action_text': _("View"),
            }
            self.project_id.message_post(body=Markup(self.project_id._get_log_message_template()).format(**template_message))

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Repository Connected'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

        except Exception as e:
            _logger.error(f"Error connecting repository: {e}")
            raise UserError(_('Failed to connect repository: %s') % str(e))

    def _create_write_branches(self, project_id, default_branch, repo_id):
        """Create or update the default branch record for the connected repository"""
        branch_model = self.env['project.github.branch']
        branch = branch_model.search([
            ('name', '=', default_branch),
            ('repository_id', '=', repo_id),
            ('project_id', '=', project_id)
        ], limit=1)

        if not branch:
            branch = branch_model.create({
                'name': default_branch,
                'repository_id': repo_id,
                'project_id': project_id,
                'is_default': True,
            })
        else:
            branch.write({'is_default': True})
        return branch