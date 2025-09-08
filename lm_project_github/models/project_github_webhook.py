from odoo import fields, models, api, _
import requests
from odoo.exceptions import UserError


class ProjectGithubWebhook(models.Model):
    _name = 'project.github.webhook'
    _description = 'GitHub Webhook Configuration'

    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        help='Project to configure the GitHub webhook for',
    )
    webhook_id = fields.Char(
        string='Webhook ID',
        readonly=True,
        help='ID of the webhook in GitHub',
    )
    webhook_name = fields.Char(
        string='Webhook Name',
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
                self.webhook_id = str(webhook_data.get('id'))
                self.project_id.write({'webhook_id': self.id})
                self.project_id.message_post(
                    body=_("GitHub webhook created successfully with ID: %s") % self.webhook_id
                )
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
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/github/webhook/{self.id}"