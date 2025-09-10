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
    name = fields.Char(
        string='Name',
        required=True,
        help='Name of the webhook in GitHub',
    )
    repository_id = fields.Many2one(
        'project.github.repository',
        string='Repository',
        required=True,
        help='GitHub repository to associate the webhook with',
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