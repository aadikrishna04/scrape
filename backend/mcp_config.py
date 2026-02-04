"""
MCP Configuration - Default server configurations
"""
import os
from typing import List, Optional
from dataclasses import dataclass, field
from mcp_manager import MCPServerConfig


@dataclass
class IntegrationRequirement:
    """Defines what's needed to connect an integration."""
    type: str  # 'token', 'oauth', 'none'
    name: str  # Display name for the credential
    description: str  # Help text
    env_var: str  # Environment variable name
    help_url: Optional[str] = None  # URL to get the credential
    required_scopes: Optional[List[str]] = None  # Required permissions/scopes
    setup_steps: Optional[List[str]] = None  # Step-by-step setup instructions
    validation_endpoint: Optional[str] = None  # API endpoint to validate token


# Integration requirements for each server
INTEGRATION_REQUIREMENTS = {
    "github": IntegrationRequirement(
        type="oauth",
        name="GitHub OAuth",
        description="Connect with GitHub to manage repositories, issues, and pull requests.",
        env_var="",
        help_url="https://github.com/settings/developers",
        required_scopes=["repo", "read:user", "read:org", "workflow"],
        setup_steps=None,  # OAuth - no manual steps
        validation_endpoint="https://api.github.com/user"
    ),
    "slack": IntegrationRequirement(
        type="token",
        name="Bot Token",
        description="Slack Bot User OAuth Token (starts with xoxb-)",
        env_var="SLACK_BOT_TOKEN",
        help_url="https://api.slack.com/apps",
        required_scopes=["chat:write", "channels:read", "channels:history", "users:read", "im:write"],
        setup_steps=[
            "Go to api.slack.com/apps and click 'Create New App'",
            "Choose 'From scratch', name it, and select your workspace",
            "Go to 'OAuth & Permissions' in the sidebar",
            "Under 'Scopes' → 'Bot Token Scopes', add: chat:write, channels:read, channels:history, users:read",
            "Click 'Install to Workspace' and authorize",
            "Copy the 'Bot User OAuth Token' (starts with xoxb-)"
        ],
        validation_endpoint="https://slack.com/api/auth.test"
    ),
    "brave-search": IntegrationRequirement(
        type="token",
        name="API Key",
        description="Brave Search API key for web search",
        env_var="BRAVE_API_KEY",
        help_url="https://brave.com/search/api/",
        required_scopes=None,
        setup_steps=[
            "Go to brave.com/search/api and sign up",
            "Create a new API key",
            "Copy the API key"
        ],
        validation_endpoint=None  # Will test with a search query
    ),
    "postgres": IntegrationRequirement(
        type="token",
        name="Connection URL",
        description="PostgreSQL connection string",
        env_var="DATABASE_URL",
        help_url=None,
        required_scopes=None,
        setup_steps=[
            "Format: postgresql://username:password@host:port/database",
            "Ensure the user has SELECT, INSERT, UPDATE, DELETE permissions",
            "For read-only access, SELECT permission is sufficient"
        ],
        validation_endpoint=None  # Will test with a connection attempt
    ),
    "notion": IntegrationRequirement(
        type="token",
        name="Integration Token",
        description="Notion Internal Integration Token (starts with secret_)",
        env_var="NOTION_TOKEN",
        help_url="https://www.notion.so/my-integrations",
        required_scopes=["Read content", "Insert content", "Update content"],
        setup_steps=[
            "Go to notion.so/my-integrations",
            "Click '+ New integration'",
            "Name it (e.g., 'Sentric') and select your workspace",
            "Under 'Capabilities', enable: Read content, Insert content, Update content",
            "Click 'Submit' and copy the 'Internal Integration Token'",
            "IMPORTANT: Share pages/databases with the integration (click '...' → 'Add connections')"
        ],
        validation_endpoint="https://api.notion.com/v1/users/me"
    ),
    "linear": IntegrationRequirement(
        type="oauth",
        name="Linear Account",
        description="Linear uses OAuth - authenticate via Linear's official MCP server",
        env_var="",
        help_url="https://linear.app/docs/mcp",
        required_scopes=["read", "write", "issues:create", "comments:create"],
        setup_steps=[
            "Linear's MCP server handles authentication automatically",
            "When connecting, you'll be redirected to Linear to authorize",
            "No API key needed - uses official Linear OAuth"
        ],
        validation_endpoint=None
    ),
    "jira": IntegrationRequirement(
        type="token",
        name="API Token",
        description="Atlassian API Token (paste as: email:token)",
        env_var="JIRA_API_TOKEN",
        help_url="https://id.atlassian.com/manage-profile/security/api-tokens",
        required_scopes=["read:jira-work", "write:jira-work", "read:jira-user"],
        setup_steps=[
            "Go to id.atlassian.com/manage-profile/security/api-tokens",
            "Click 'Create API token'",
            "Name it (e.g., 'Sentric')",
            "Copy the token",
            "Paste in this format: your-email@example.com:your-api-token",
            "Note your Jira URL (e.g., yourcompany.atlassian.net)"
        ],
        validation_endpoint=None  # Requires Jira URL
    ),
    "gmail": IntegrationRequirement(
        type="oauth",
        name="Gmail",
        description="Connect with Google to send and read emails. Uses web OAuth flow.",
        env_var="",
        help_url="https://console.cloud.google.com/apis/credentials",
        required_scopes=["gmail.send", "gmail.readonly", "gmail.compose"],
        setup_steps=None,  # OAuth - no manual steps
        validation_endpoint="https://gmail.googleapis.com/gmail/v1/users/me/profile"
    ),
    "google-calendar": IntegrationRequirement(
        type="oauth",
        name="Google Calendar",
        description="Connect with Google to manage calendar events. Uses web OAuth flow.",
        env_var="",
        help_url="https://console.cloud.google.com/apis/credentials",
        required_scopes=["calendar.events", "calendar.readonly"],
        setup_steps=None,  # OAuth - no manual steps
        validation_endpoint="https://www.googleapis.com/calendar/v3/calendars/primary"
    ),
    "google-drive": IntegrationRequirement(
        type="oauth",
        name="Google Drive",
        description="Connect with Google to manage Drive files. Uses web OAuth flow.",
        env_var="",
        help_url="https://console.cloud.google.com/apis/credentials",
        required_scopes=["drive.file", "drive.readonly"],
        setup_steps=None,  # OAuth - no manual steps
        validation_endpoint="https://www.googleapis.com/drive/v3/about?fields=user"
    ),
    "airtable": IntegrationRequirement(
        type="token",
        name="Personal Access Token",
        description="Airtable Personal Access Token",
        env_var="AIRTABLE_API_KEY",
        help_url="https://airtable.com/create/tokens",
        required_scopes=["data.records:read", "data.records:write", "schema.bases:read"],
        setup_steps=[
            "Go to airtable.com/create/tokens",
            "Click 'Create new token'",
            "Name it (e.g., 'Sentric')",
            "Add scopes: data.records:read, data.records:write, schema.bases:read",
            "Under 'Access', add the bases you want to access (or 'All current and future bases')",
            "Click 'Create token' and copy it"
        ],
        validation_endpoint="https://api.airtable.com/v0/meta/whoami"
    ),
    "twilio": IntegrationRequirement(
        type="token",
        name="Account SID, API Key & Secret",
        description="Twilio credentials (paste as: account_sid/api_key:api_secret)",
        env_var="TWILIO_CREDENTIALS",
        help_url="https://console.twilio.com/",
        required_scopes=None,
        setup_steps=[
            "Go to console.twilio.com",
            "Find 'Account SID' on the dashboard (starts with AC)",
            "Go to Account → API Keys & Tokens → Create API Key",
            "Copy the SID (starts with SK) and Secret",
            "Paste in this format: ACXXXXXXXXX/SKXXXXXXXXX:your_api_secret",
            "To send SMS, you'll also need a Twilio phone number"
        ],
        validation_endpoint="https://api.twilio.com/2010-04-01/Accounts"
    ),
    "sendgrid": IntegrationRequirement(
        type="token",
        name="API Key",
        description="SendGrid API Key (starts with SG.)",
        env_var="SENDGRID_API_KEY",
        help_url="https://app.sendgrid.com/settings/api_keys",
        required_scopes=["Mail Send"],
        setup_steps=[
            "Go to app.sendgrid.com/settings/api_keys",
            "Click 'Create API Key'",
            "Name it (e.g., 'Sentric')",
            "Choose 'Restricted Access' and enable 'Mail Send' → 'Full Access'",
            "Click 'Create & View' and copy the key (starts with SG.)"
        ],
        validation_endpoint=None  # SendGrid doesn't have a simple validation endpoint
    ),
    "stripe": IntegrationRequirement(
        type="token",
        name="Secret Key",
        description="Stripe Secret Key (starts with sk_test_ or sk_live_)",
        env_var="STRIPE_SECRET_KEY",
        help_url="https://dashboard.stripe.com/apikeys",
        required_scopes=None,
        setup_steps=[
            "Go to dashboard.stripe.com/apikeys",
            "Copy the 'Secret key' (click to reveal)",
            "Use sk_test_... for testing, sk_live_... for production",
            "WARNING: Live keys can charge real money!"
        ],
        validation_endpoint="https://api.stripe.com/v1/balance"
    ),
    "discord": IntegrationRequirement(
        type="token",
        name="Bot Token",
        description="Discord Bot Token",
        env_var="DISCORD_BOT_TOKEN",
        help_url="https://discord.com/developers/applications",
        required_scopes=["Send Messages", "Read Message History", "Embed Links"],
        setup_steps=[
            "Go to discord.com/developers/applications",
            "Click 'New Application' and name it",
            "Go to 'Bot' in sidebar → 'Add Bot'",
            "Under 'Privileged Gateway Intents', enable 'Message Content Intent'",
            "Copy the token (click 'Reset Token' if needed)",
            "Go to 'OAuth2' → 'URL Generator', select 'bot' scope",
            "Select permissions: Send Messages, Read Message History",
            "Use generated URL to invite bot to your server"
        ],
        validation_endpoint="https://discord.com/api/v10/users/@me"
    ),
    "trello": IntegrationRequirement(
        type="token",
        name="API Key & Token",
        description="Trello API Key and Token (paste as: api_key:token)",
        env_var="TRELLO_TOKEN",
        help_url="https://trello.com/app-key",
        required_scopes=["read", "write"],
        setup_steps=[
            "Go to trello.com/app-key",
            "Copy your API Key",
            "Click the 'Token' link to generate a token",
            "Authorize and copy the token",
            "Paste in this format: your_api_key:your_token"
        ],
        validation_endpoint="https://api.trello.com/1/members/me"
    ),
    "mongodb": IntegrationRequirement(
        type="token",
        name="Connection URI",
        description="MongoDB connection string",
        env_var="MONGODB_URI",
        help_url="https://cloud.mongodb.com/",
        required_scopes=None,
        setup_steps=[
            "In MongoDB Atlas, go to your cluster",
            "Click 'Connect' → 'Connect your application'",
            "Copy the connection string",
            "Replace <password> with your database user password",
            "Add your database name at the end: mongodb+srv://...mongodb.net/mydb"
        ],
        validation_endpoint=None  # Requires actual connection
    ),
    "redis": IntegrationRequirement(
        type="token",
        name="Connection URL",
        description="Redis connection URL",
        env_var="REDIS_URL",
        help_url="https://redis.com/try-free/",
        required_scopes=None,
        setup_steps=[
            "Format: redis://username:password@host:port",
            "For Redis Cloud: get URL from database details page",
            "For local Redis: redis://localhost:6379"
        ],
        validation_endpoint=None  # Requires actual connection
    ),
    "aws": IntegrationRequirement(
        type="token",
        name="Access Key & Secret",
        description="AWS credentials (paste as: access_key_id:secret_access_key:region)",
        env_var="AWS_ACCESS_KEY_ID",
        help_url="https://console.aws.amazon.com/iam/",
        required_scopes=["s3:*", "lambda:InvokeFunction", "ses:SendEmail"],
        setup_steps=[
            "Go to AWS IAM Console → Users → Add user",
            "Enable 'Access key - Programmatic access'",
            "Attach policies for services you need (e.g., AmazonS3FullAccess)",
            "Copy Access Key ID and Secret Access Key",
            "Paste in format: AKIAXXXXXXXX:secret_key:us-east-1"
        ],
        validation_endpoint="https://sts.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15"
    ),
}


def get_default_configs() -> List[MCPServerConfig]:
    """Get default MCP server configurations."""
    return [
        # Built-in browser automation (internal, always enabled)
        MCPServerConfig(
            name="browser",
            display_name="Browser Automation",
            command="internal",
            args=[],
            env={},
            enabled=True,
            icon="globe"
        ),

        # Built-in AI processing (internal, always enabled)
        MCPServerConfig(
            name="ai",
            display_name="AI Processing",
            command="internal",
            args=[],
            env={},
            enabled=True,
            icon="zap"
        ),

        # GitHub MCP Server (using npx - no Docker required)
        MCPServerConfig(
            name="github",
            display_name="GitHub",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"},
            enabled=False,
            icon="github"
        ),

        # Slack MCP Server
        MCPServerConfig(
            name="slack",
            display_name="Slack",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-slack"],
            env={"SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}"},
            enabled=False,
            icon="slack"
        ),

        # Google Drive (internal - uses our OAuth tokens)
        MCPServerConfig(
            name="google-drive",
            display_name="Google Drive",
            command="internal",
            args=[],
            env={},
            enabled=True,
            icon="cloud"
        ),

        # Filesystem MCP Server (always enabled for workspace file operations)
        MCPServerConfig(
            name="filesystem",
            display_name="File System",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", os.path.join(os.path.dirname(__file__), "workspace")],
            env={},
            enabled=True,
            icon="folder"
        ),

        # Brave Search MCP Server
        MCPServerConfig(
            name="brave-search",
            display_name="Brave Search",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-brave-search"],
            env={"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
            enabled=False,
            icon="search"
        ),

        # PostgreSQL MCP Server (deprecated but still available)
        MCPServerConfig(
            name="postgres",
            display_name="PostgreSQL",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-postgres", "${DATABASE_URL}"],
            env={},
            enabled=False,
            icon="database"
        ),

        # ===== NEW INTEGRATIONS =====

        # Notion MCP Server (official)
        MCPServerConfig(
            name="notion",
            display_name="Notion",
            command="npx",
            args=["-y", "@notionhq/notion-mcp-server"],
            env={"OPENAPI_MCP_HEADERS": '{"Authorization": "Bearer ${NOTION_TOKEN}", "Notion-Version": "2022-06-28"}'},
            enabled=False,
            icon="notion"
        ),

        # Linear MCP Server (official remote server)
        MCPServerConfig(
            name="linear",
            display_name="Linear",
            command="npx",
            args=["-y", "mcp-remote", "https://mcp.linear.app/sse"],
            env={},
            enabled=False,
            icon="linear"
        ),

        # Jira MCP Server (community package)
        MCPServerConfig(
            name="jira",
            display_name="Jira",
            command="npx",
            args=["-y", "@aot-tech/jira-mcp-server"],
            env={
                "JIRA_API_TOKEN": "${JIRA_API_TOKEN}",
                "JIRA_USER_EMAIL": "${JIRA_EMAIL}",
                "JIRA_BASE_URL": "${JIRA_URL}"
            },
            enabled=False,
            icon="jira"
        ),

        # Gmail (internal - uses our OAuth tokens)
        MCPServerConfig(
            name="gmail",
            display_name="Gmail",
            command="internal",
            args=[],
            env={},
            enabled=True,
            icon="mail"
        ),

        # Google Calendar (internal - uses our OAuth tokens)
        MCPServerConfig(
            name="google-calendar",
            display_name="Google Calendar",
            command="internal",
            args=[],
            env={},
            enabled=True,
            icon="calendar"
        ),

        # Airtable MCP Server (community package)
        MCPServerConfig(
            name="airtable",
            display_name="Airtable",
            command="npx",
            args=["-y", "airtable-mcp-server"],
            env={"AIRTABLE_API_KEY": "${AIRTABLE_API_KEY}"},
            enabled=False,
            icon="table"
        ),

        # Twilio MCP Server (official alpha)
        MCPServerConfig(
            name="twilio",
            display_name="Twilio",
            command="npx",
            args=["-y", "@twilio-alpha/mcp", "${TWILIO_ACCOUNT_SID}/${TWILIO_API_KEY}:${TWILIO_API_SECRET}"],
            env={},
            enabled=False,
            icon="phone"
        ),

        # SendGrid MCP Server (community package)
        MCPServerConfig(
            name="sendgrid",
            display_name="SendGrid",
            command="npx",
            args=["-y", "sendgrid-api-mcp-server"],
            env={
                "SENDGRID_API_KEY": "${SENDGRID_API_KEY}",
                "FROM_EMAIL": "${SENDGRID_FROM_EMAIL}"
            },
            enabled=False,
            icon="mail"
        ),

        # Stripe MCP Server (official)
        MCPServerConfig(
            name="stripe",
            display_name="Stripe",
            command="npx",
            args=["-y", "@stripe/mcp", "--tools=all", "--api-key=${STRIPE_SECRET_KEY}"],
            env={},
            enabled=False,
            icon="credit-card"
        ),

        # Discord MCP Server (community package)
        MCPServerConfig(
            name="discord",
            display_name="Discord",
            command="npx",
            args=["-y", "@missionsquad/mcp-discord"],
            env={"DISCORD_TOKEN": "${DISCORD_BOT_TOKEN}"},
            enabled=False,
            icon="message-circle"
        ),

        # Trello MCP Server (community package)
        MCPServerConfig(
            name="trello",
            display_name="Trello",
            command="npx",
            args=["-y", "mcp-server-trello"],
            env={
                "TRELLO_API_KEY": "${TRELLO_API_KEY}",
                "TRELLO_TOKEN": "${TRELLO_TOKEN}"
            },
            enabled=False,
            icon="trello"
        ),

        # MongoDB MCP Server (official)
        MCPServerConfig(
            name="mongodb",
            display_name="MongoDB",
            command="npx",
            args=["-y", "@mongodb-js/mongodb-mcp-server"],
            env={"MCP_MONGODB_URI": "${MONGODB_URI}"},
            enabled=False,
            icon="database"
        ),

        # Redis MCP Server
        MCPServerConfig(
            name="redis",
            display_name="Redis",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-redis", "${REDIS_URL}"],
            env={},
            enabled=False,
            icon="database"
        ),

        # AWS MCP Server (Docker-based - requires Docker)
        # Note: AWS MCP uses Docker, not npm. Run with:
        # docker run -i --rm -v ~/.aws:/home/appuser/.aws:ro ghcr.io/alexei-led/aws-mcp-server:latest
        MCPServerConfig(
            name="aws",
            display_name="AWS",
            command="docker",
            args=["run", "-i", "--rm", "-e", "AWS_ACCESS_KEY_ID", "-e", "AWS_SECRET_ACCESS_KEY", "-e", "AWS_REGION", "ghcr.io/alexei-led/aws-mcp-server:latest"],
            env={
                "AWS_ACCESS_KEY_ID": "${AWS_ACCESS_KEY_ID}",
                "AWS_SECRET_ACCESS_KEY": "${AWS_SECRET_ACCESS_KEY}",
                "AWS_REGION": "${AWS_REGION}"
            },
            enabled=False,
            icon="cloud"
        ),
    ]


# Pre-defined tool categories for UI organization
TOOL_CATEGORIES = {
    "browser": {
        "name": "Browser Automation",
        "description": "Web scraping, navigation, and form interaction",
        "icon": "globe",
    },
    "code": {
        "name": "Code & Development",
        "description": "GitHub, Git, and code management tools",
        "icon": "code",
    },
    "communication": {
        "name": "Communication",
        "description": "Slack, Discord, email, and messaging tools",
        "icon": "message-square",
    },
    "storage": {
        "name": "Storage & Files",
        "description": "File systems, cloud storage, and databases",
        "icon": "folder",
    },
    "search": {
        "name": "Search & Research",
        "description": "Web search and information retrieval",
        "icon": "search",
    },
    "ai": {
        "name": "AI Processing",
        "description": "AI-powered data transformation and analysis",
        "icon": "brain",
    },
    "productivity": {
        "name": "Productivity",
        "description": "Notion, Linear, Jira, Trello, and task management",
        "icon": "check-square",
    },
    "data": {
        "name": "Data & Databases",
        "description": "PostgreSQL, MongoDB, Redis, and Airtable",
        "icon": "database",
    },
    "payments": {
        "name": "Payments & Commerce",
        "description": "Stripe and payment processing",
        "icon": "credit-card",
    },
    "cloud": {
        "name": "Cloud & Infrastructure",
        "description": "AWS and cloud infrastructure tools",
        "icon": "cloud",
    },
}
