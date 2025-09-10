from odoo import fields, models, api, _
import requests
from odoo.exceptions import UserError


class ProjectGithubCreateWebhook(models.TransientModel):
    _name = 'project.github.create.webhook'
    _description = 'GitHub Create Webhook'

    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        help='Project to configure the GitHub webhook for',
    )
    webhook_name = fields.Char(
        string='Name',
        required=True,
        help='Name of the webhook in GitHub',
    )
    push_events = fields.Boolean(
        string='Push Events',
        help='Enable push events for the webhook',
        default=True,
        readonly=True,
    )
    pull_request_events = fields.Boolean(
        string='Pull Request Events',
        help='Enable pull request events for the webhook',
        default=False,
    )
    issues_events = fields.Boolean(
        string='Issues Events',
        help='Enable issues events for the webhook',
        default=False,
    )
    workflow_jobs_events = fields.Boolean(
        string='Workflow Jobs Events',
        help='Enable workflow jobs events for the webhook',
        default=False,
    )
    enable_ssl_verification = fields.Boolean(
        string='Enable SSL Verification',
        help='Enable SSL verification for the webhook',
        default=False,
    )
    webhook_secret = fields.Char(
        string='Webhook Secret',
        help='Secret for securing the webhook',
    )

    def _header_authentication(self):
        token = self.env.user.git_token
        if not token:
            raise UserError(_("GitHub token not found in user settings. Please set it to proceed."))
        return {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
        }

    def _get_webhook_secret(self):
        if not self.webhook_secret:
            raise UserError(_("Please set a webhook secret for this configuration."))
        return self.webhook_secret

    def action_push_webhook(self):
        self.ensure_one()
        repo = self.project_id.repository_id
        if not repo or not repo.is_connected:
            raise UserError(_("Please connect a GitHub repository to the project before adding a webhook."))

        base_url = self.env.company.github_instance_url or 'https://api.github.com'

        try:
            response = requests.post(
                f"{base_url}/repos/{repo.full_name}/hooks",
                headers=self._header_authentication(),
                json={
                    "name": "web",
                    "active": True,
                    "events": self._get_selected_events(),
                    "config": {
                        "url": self._webhook_url(),
                        "content_type": "json",
                        "insecure_ssl": "1" if self.enable_ssl_verification else "0",
                        "secret": self._get_webhook_secret(),
                    },
                },
                timeout=10,
            )
            if response.status_code == 201:
                webhook_data = response.json()
                weebhook = self.env['project.github.webhook'].create({
                    'name': self.webhook_name,
                    'webhook_id': webhook_data.get('id'),
                    'project_id': self.project_id.id,
                    'repository_id': repo.id,
                    'push_events': self.push_events,
                    'pull_request_events': self.pull_request_events,
                    'issues_events': self.issues_events,
                    'workflow_jobs_events': self.workflow_jobs_events,
                    'enable_ssl_verification': self.enable_ssl_verification,
                    'webhook_secret': self.webhook_secret,
                })
                self.project_id.write({'project_webhook_id': weebhook.id})
                self.project_id.message_post(
                    body=_("GitHub webhook created successfully with ID: %s") % weebhook.webhook_id
                )
            else:
                error_message = response.json().get('errors', response.json().get('message', 'Unknown error'))
                raise UserError(_("Failed to create webhook: %s") % error_message)
        except requests.RequestException as e:
            raise UserError(_("Failed to create webhook: %s") % str(e))

    def _get_selected_events(self):
        events = []
        if self.push_events:
            events.append("push")
        if self.pull_request_events:
            events.append("pull_request")
        if self.issues_events:
            events.append("issues")
        if self.workflow_jobs_events:
            events.append("workflow_job")
        return events or ["push"]

    def _webhook_url(self):
        # base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        base_url = "https://a0d6ef0be552.ngrok-free.app"
        return f"{base_url}/github/webhook/{self.id}"