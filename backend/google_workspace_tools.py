"""
Google Workspace Tools - Internal tools for Gmail, Calendar, and Drive
Uses stored OAuth tokens from user_integration_tokens table
"""
import os
import json
import base64
from typing import Dict, Any, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import httpx

from mcp_manager import MCPManager, MCPTool


# Google API base URLs
GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"
DRIVE_API = "https://www.googleapis.com/drive/v3"


async def _get_access_token(context: Optional[Dict[str, Any]], provider: str) -> Optional[str]:
    """
    Get OAuth access token from context.
    The context should contain 'user_id' and the token resolver will be called.
    """
    if not context:
        print(f"[GoogleAuth] No context provided for {provider}")
        return None

    # If token is directly in context (passed from handler)
    if f"{provider}_token" in context:
        print(f"[GoogleAuth] Found {provider}_token directly in context")
        return context[f"{provider}_token"]

    # Try to get token via resolver in context
    token_resolver = context.get("_token_resolver")
    user_id = context.get("user_id")

    print(f"[GoogleAuth] Looking up token for {provider}, user_id={user_id[:8] if user_id else 'None'}...")

    if token_resolver and user_id:
        token_data = token_resolver(user_id, provider)
        if token_data:
            print(f"[GoogleAuth] Found token data for {provider} (length: {len(token_data)})")
            # Token might be JSON string with access_token, or just the token
            if isinstance(token_data, str):
                try:
                    parsed = json.loads(token_data)
                    access_token = parsed.get("access_token", token_data)
                    print(f"[GoogleAuth] Parsed access_token (length: {len(access_token) if access_token else 0})")
                    return access_token
                except json.JSONDecodeError:
                    return token_data
            return token_data
        else:
            print(f"[GoogleAuth] No token found in DB for {provider}")
    else:
        print(f"[GoogleAuth] Missing resolver or user_id: resolver={token_resolver is not None}, user_id={user_id is not None}")

    return None


async def _make_google_request(
    method: str,
    url: str,
    token: str,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Make an authenticated request to Google APIs."""
    default_headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if headers:
        default_headers.update(headers)

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
            content=data,
            headers=default_headers,
            timeout=30.0
        )

        if response.status_code == 401:
            return {"success": False, "error": "Token expired. Please reconnect Gmail in Settings."}

        if response.status_code >= 400:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
            except:
                error_msg = response.text
            return {"success": False, "error": f"Google API error: {error_msg}"}

        try:
            return {"success": True, "data": response.json()}
        except:
            return {"success": True, "data": response.text}


# ============= GMAIL TOOLS =============

def get_gmail_tools() -> List[MCPTool]:
    """Return Gmail tools in MCP format."""
    return [
        MCPTool(
            name="gmail.list_emails",
            server_name="gmail",
            original_name="list_emails",
            display_name="List Emails",
            description="List or search emails in Gmail inbox. Can filter by query (from:, to:, subject:, is:unread, etc).",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'from:alice@example.com', 'is:unread', 'subject:meeting'). Leave empty for recent emails."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of emails to return (default: 10, max: 50)",
                        "default": 10
                    }
                },
                "required": []
            },
            category="gmail"
        ),
        MCPTool(
            name="gmail.read_email",
            server_name="gmail",
            original_name="read_email",
            display_name="Read Email",
            description="Read the full content of a specific email by ID.",
            input_schema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "The email ID (from list_emails result)"
                    }
                },
                "required": ["email_id"]
            },
            category="gmail"
        ),
        MCPTool(
            name="gmail.send_email",
            server_name="gmail",
            original_name="send_email",
            display_name="Send Email",
            description="Send a new email.",
            input_schema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address(es), comma-separated for multiple"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content (plain text or HTML)"
                    },
                    "cc": {
                        "type": "string",
                        "description": "CC recipients, comma-separated (optional)"
                    },
                    "bcc": {
                        "type": "string",
                        "description": "BCC recipients, comma-separated (optional)"
                    },
                    "html": {
                        "type": "boolean",
                        "description": "Whether the body is HTML (default: false)",
                        "default": False
                    }
                },
                "required": ["to", "subject", "body"]
            },
            category="gmail"
        ),
        MCPTool(
            name="gmail.reply_to_email",
            server_name="gmail",
            original_name="reply_to_email",
            display_name="Reply to Email",
            description="Reply to an existing email thread.",
            input_schema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "The email ID to reply to"
                    },
                    "body": {
                        "type": "string",
                        "description": "Reply content"
                    },
                    "reply_all": {
                        "type": "boolean",
                        "description": "Whether to reply to all recipients (default: false)",
                        "default": False
                    }
                },
                "required": ["email_id", "body"]
            },
            category="gmail"
        ),
    ]


async def handle_gmail_tool(
    tool_name: str,
    params: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Handle Gmail tool calls."""
    print(f"[Gmail] Handling {tool_name}")
    print(f"[Gmail] Context keys: {list(context.keys()) if context else 'None'}")

    token = await _get_access_token(context, "gmail")
    if not token:
        print("[Gmail] No token found!")
        return {"success": False, "error": "Gmail not connected. Please connect Gmail in Settings → Integrations."}

    if tool_name == "gmail.list_emails":
        return await _gmail_list_emails(token, params)
    elif tool_name == "gmail.read_email":
        return await _gmail_read_email(token, params)
    elif tool_name == "gmail.send_email":
        return await _gmail_send_email(token, params)
    elif tool_name == "gmail.reply_to_email":
        return await _gmail_reply_to_email(token, params)

    return {"success": False, "error": f"Unknown Gmail tool: {tool_name}"}


async def _gmail_list_emails(token: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """List emails from Gmail."""
    query = params.get("query", "")
    max_results = min(params.get("max_results", 10), 50)

    # List messages
    result = await _make_google_request(
        "GET",
        f"{GMAIL_API}/users/me/messages",
        token,
        params={"q": query, "maxResults": max_results}
    )

    if not result.get("success"):
        return result

    messages = result["data"].get("messages", [])
    if not messages:
        return {"success": True, "result": "No emails found matching the query."}

    # Fetch details for each message
    emails = []
    for msg in messages[:max_results]:
        detail_result = await _make_google_request(
            "GET",
            f"{GMAIL_API}/users/me/messages/{msg['id']}",
            token,
            params={"format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]}
        )

        if detail_result.get("success"):
            msg_data = detail_result["data"]
            headers = {h["name"]: h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
            emails.append({
                "id": msg["id"],
                "from": headers.get("From", "Unknown"),
                "to": headers.get("To", "Unknown"),
                "subject": headers.get("Subject", "(No subject)"),
                "date": headers.get("Date", "Unknown"),
                "snippet": msg_data.get("snippet", "")[:200]
            })

    return {"success": True, "result": json.dumps(emails, indent=2)}


async def _gmail_read_email(token: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Read full email content."""
    email_id = params.get("email_id")
    if not email_id:
        return {"success": False, "error": "email_id is required"}

    result = await _make_google_request(
        "GET",
        f"{GMAIL_API}/users/me/messages/{email_id}",
        token,
        params={"format": "full"}
    )

    if not result.get("success"):
        return result

    msg_data = result["data"]
    payload = msg_data.get("payload", {})
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}

    # Extract body
    body = ""
    if "body" in payload and payload["body"].get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
    elif "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") in ["text/plain", "text/html"]:
                if part.get("body", {}).get("data"):
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                    break

    email_content = {
        "id": email_id,
        "from": headers.get("From", "Unknown"),
        "to": headers.get("To", "Unknown"),
        "subject": headers.get("Subject", "(No subject)"),
        "date": headers.get("Date", "Unknown"),
        "body": body
    }

    return {"success": True, "result": json.dumps(email_content, indent=2)}


async def _gmail_send_email(token: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Send a new email."""
    to = params.get("to", "")
    subject = params.get("subject", "")
    body = params.get("body", "")
    cc = params.get("cc", "")
    bcc = params.get("bcc", "")
    is_html = params.get("html", False)

    # Clean up 'to' field - remove newlines, extra whitespace
    if isinstance(to, str):
        # Replace newlines with commas (in case multiple emails are on separate lines)
        to = to.replace("\n", ",").replace("\r", "")
        # Split, strip, and rejoin to clean up whitespace
        to_list = [email.strip() for email in to.split(",") if email.strip()]
        # Filter to only valid-looking emails (basic check)
        valid_emails = [e for e in to_list if "@" in e and "." in e.split("@")[-1]]
        to = ", ".join(valid_emails)

    print(f"[Gmail] Sending email to: {to}")
    print(f"[Gmail] Subject: {subject}")
    print(f"[Gmail] Body preview: {str(body)[:200]}...")

    if not to:
        return {"success": False, "error": "'to' recipient is required or no valid email addresses found"}

    # Clean up cc/bcc similarly
    if isinstance(cc, str) and cc:
        cc = cc.replace("\n", ",").replace("\r", "")
        cc_list = [email.strip() for email in cc.split(",") if email.strip() and "@" in email]
        cc = ", ".join(cc_list)
    if isinstance(bcc, str) and bcc:
        bcc = bcc.replace("\n", ",").replace("\r", "")
        bcc_list = [email.strip() for email in bcc.split(",") if email.strip() and "@" in email]
        bcc = ", ".join(bcc_list)

    # Clean up subject - remove newlines
    if isinstance(subject, str):
        subject = subject.replace("\n", " ").replace("\r", "").strip()

    # Create message
    if is_html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "html"))
    else:
        msg = MIMEText(body)

    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc

    # Encode message
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    result = await _make_google_request(
        "POST",
        f"{GMAIL_API}/users/me/messages/send",
        token,
        json_body={"raw": raw}
    )

    if result.get("success"):
        return {"success": True, "result": f"Email sent successfully to {to}. Message ID: {result['data'].get('id')}"}
    return result


async def _gmail_reply_to_email(token: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Reply to an existing email."""
    email_id = params.get("email_id")
    body = params.get("body", "")
    reply_all = params.get("reply_all", False)

    if not email_id:
        return {"success": False, "error": "email_id is required"}

    # Get original message to get thread ID and reply headers
    original = await _make_google_request(
        "GET",
        f"{GMAIL_API}/users/me/messages/{email_id}",
        token,
        params={"format": "metadata", "metadataHeaders": ["From", "To", "Cc", "Subject", "Message-ID"]}
    )

    if not original.get("success"):
        return original

    orig_data = original["data"]
    headers = {h["name"]: h["value"] for h in orig_data.get("payload", {}).get("headers", [])}
    thread_id = orig_data.get("threadId")

    # Build reply recipients
    to = headers.get("From", "")
    cc = ""
    if reply_all:
        original_to = headers.get("To", "")
        original_cc = headers.get("Cc", "")
        all_recipients = set()
        if original_to:
            all_recipients.update([r.strip() for r in original_to.split(",")])
        if original_cc:
            all_recipients.update([r.strip() for r in original_cc.split(",")])
        all_recipients.discard(to)  # Don't include original sender in CC
        cc = ", ".join(all_recipients)

    # Create reply message
    subject = headers.get("Subject", "")
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    msg = MIMEText(body)
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    msg["In-Reply-To"] = headers.get("Message-ID", "")
    msg["References"] = headers.get("Message-ID", "")

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    result = await _make_google_request(
        "POST",
        f"{GMAIL_API}/users/me/messages/send",
        token,
        json_body={"raw": raw, "threadId": thread_id}
    )

    if result.get("success"):
        return {"success": True, "result": f"Reply sent successfully. Message ID: {result['data'].get('id')}"}
    return result


# ============= CALENDAR TOOLS =============

def get_calendar_tools() -> List[MCPTool]:
    """Return Google Calendar tools in MCP format."""
    return [
        MCPTool(
            name="calendar.list_events",
            server_name="google-calendar",
            original_name="list_events",
            display_name="List Calendar Events",
            description="List upcoming events from Google Calendar.",
            input_schema={
                "type": "object",
                "properties": {
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID (default: 'primary' for main calendar)",
                        "default": "primary"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of events to return (default: 10)",
                        "default": 10
                    },
                    "days_ahead": {
                        "type": "integer",
                        "description": "Number of days ahead to look for events (default: 7)",
                        "default": 7
                    }
                },
                "required": []
            },
            category="calendar"
        ),
        MCPTool(
            name="calendar.create_event",
            server_name="google-calendar",
            original_name="create_event",
            display_name="Create Calendar Event",
            description="Create a new event on Google Calendar.",
            input_schema={
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Event title"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO format (e.g., '2024-01-15T10:00:00') or natural language"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO format or natural language"
                    },
                    "description": {
                        "type": "string",
                        "description": "Event description (optional)"
                    },
                    "location": {
                        "type": "string",
                        "description": "Event location (optional)"
                    },
                    "attendees": {
                        "type": "string",
                        "description": "Comma-separated email addresses of attendees (optional)"
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID (default: 'primary')",
                        "default": "primary"
                    }
                },
                "required": ["summary", "start_time", "end_time"]
            },
            category="calendar"
        ),
        MCPTool(
            name="calendar.delete_event",
            server_name="google-calendar",
            original_name="delete_event",
            display_name="Delete Calendar Event",
            description="Delete an event from Google Calendar.",
            input_schema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The event ID to delete"
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID (default: 'primary')",
                        "default": "primary"
                    }
                },
                "required": ["event_id"]
            },
            category="calendar"
        ),
    ]


async def handle_calendar_tool(
    tool_name: str,
    params: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Handle Calendar tool calls."""
    token = await _get_access_token(context, "google-calendar")
    if not token:
        return {"success": False, "error": "Google Calendar not connected. Please connect it in Settings → Integrations."}

    if tool_name == "calendar.list_events":
        return await _calendar_list_events(token, params)
    elif tool_name == "calendar.create_event":
        return await _calendar_create_event(token, params)
    elif tool_name == "calendar.delete_event":
        return await _calendar_delete_event(token, params)

    return {"success": False, "error": f"Unknown Calendar tool: {tool_name}"}


async def _calendar_list_events(token: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """List upcoming calendar events."""
    calendar_id = params.get("calendar_id", "primary")
    max_results = min(params.get("max_results", 10), 50)
    days_ahead = params.get("days_ahead", 7)

    now = datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"

    result = await _make_google_request(
        "GET",
        f"{CALENDAR_API}/calendars/{calendar_id}/events",
        token,
        params={
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime"
        }
    )

    if not result.get("success"):
        return result

    events = result["data"].get("items", [])
    if not events:
        return {"success": True, "result": "No upcoming events found."}

    formatted_events = []
    for event in events:
        start = event.get("start", {}).get("dateTime", event.get("start", {}).get("date", "Unknown"))
        end = event.get("end", {}).get("dateTime", event.get("end", {}).get("date", "Unknown"))
        formatted_events.append({
            "id": event.get("id"),
            "summary": event.get("summary", "(No title)"),
            "start": start,
            "end": end,
            "location": event.get("location", ""),
            "description": event.get("description", "")[:200] if event.get("description") else ""
        })

    return {"success": True, "result": json.dumps(formatted_events, indent=2)}


async def _calendar_create_event(token: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new calendar event."""
    calendar_id = params.get("calendar_id", "primary")
    summary = params.get("summary")
    start_time = params.get("start_time")
    end_time = params.get("end_time")
    description = params.get("description", "")
    location = params.get("location", "")
    attendees_str = params.get("attendees", "")

    if not summary or not start_time or not end_time:
        return {"success": False, "error": "summary, start_time, and end_time are required"}

    event = {
        "summary": summary,
        "start": {"dateTime": start_time, "timeZone": "UTC"},
        "end": {"dateTime": end_time, "timeZone": "UTC"},
    }

    if description:
        event["description"] = description
    if location:
        event["location"] = location
    if attendees_str:
        attendees = [{"email": e.strip()} for e in attendees_str.split(",") if e.strip()]
        event["attendees"] = attendees

    result = await _make_google_request(
        "POST",
        f"{CALENDAR_API}/calendars/{calendar_id}/events",
        token,
        json_body=event
    )

    if result.get("success"):
        created = result["data"]
        return {"success": True, "result": f"Event created: {created.get('summary')} (ID: {created.get('id')})"}
    return result


async def _calendar_delete_event(token: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a calendar event."""
    calendar_id = params.get("calendar_id", "primary")
    event_id = params.get("event_id")

    if not event_id:
        return {"success": False, "error": "event_id is required"}

    result = await _make_google_request(
        "DELETE",
        f"{CALENDAR_API}/calendars/{calendar_id}/events/{event_id}",
        token
    )

    if result.get("success") or result.get("data") == "":
        return {"success": True, "result": f"Event {event_id} deleted successfully."}
    return result


# ============= DRIVE TOOLS =============

def get_drive_tools() -> List[MCPTool]:
    """Return Google Drive tools in MCP format."""
    return [
        MCPTool(
            name="drive.list_files",
            server_name="google-drive",
            original_name="list_files",
            display_name="List Drive Files",
            description="List files in Google Drive.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., \"name contains 'report'\"). Leave empty for recent files."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of files to return (default: 10)",
                        "default": 10
                    },
                    "folder_id": {
                        "type": "string",
                        "description": "Folder ID to list files from (optional, defaults to all files)"
                    }
                },
                "required": []
            },
            category="drive"
        ),
        MCPTool(
            name="drive.read_file",
            server_name="google-drive",
            original_name="read_file",
            display_name="Read Drive File",
            description="Read the content of a file from Google Drive (text files, docs, sheets).",
            input_schema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The file ID to read"
                    }
                },
                "required": ["file_id"]
            },
            category="drive"
        ),
        MCPTool(
            name="drive.search_files",
            server_name="google-drive",
            original_name="search_files",
            display_name="Search Drive Files",
            description="Search for files in Google Drive by name or content.",
            input_schema={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "Text to search for in file names and content"
                    },
                    "file_type": {
                        "type": "string",
                        "description": "Filter by file type: 'document', 'spreadsheet', 'presentation', 'pdf', 'image', 'folder'",
                        "enum": ["document", "spreadsheet", "presentation", "pdf", "image", "folder"]
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)",
                        "default": 10
                    }
                },
                "required": ["search_term"]
            },
            category="drive"
        ),
    ]


async def handle_drive_tool(
    tool_name: str,
    params: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Handle Drive tool calls."""
    token = await _get_access_token(context, "google-drive")
    if not token:
        return {"success": False, "error": "Google Drive not connected. Please connect it in Settings → Integrations."}

    if tool_name == "drive.list_files":
        return await _drive_list_files(token, params)
    elif tool_name == "drive.read_file":
        return await _drive_read_file(token, params)
    elif tool_name == "drive.search_files":
        return await _drive_search_files(token, params)

    return {"success": False, "error": f"Unknown Drive tool: {tool_name}"}


async def _drive_list_files(token: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """List files in Google Drive."""
    query = params.get("query", "")
    max_results = min(params.get("max_results", 10), 100)
    folder_id = params.get("folder_id")

    q_parts = []
    if query:
        q_parts.append(query)
    if folder_id:
        q_parts.append(f"'{folder_id}' in parents")
    q_parts.append("trashed = false")

    result = await _make_google_request(
        "GET",
        f"{DRIVE_API}/files",
        token,
        params={
            "q": " and ".join(q_parts) if q_parts else None,
            "pageSize": max_results,
            "fields": "files(id, name, mimeType, modifiedTime, size, webViewLink)",
            "orderBy": "modifiedTime desc"
        }
    )

    if not result.get("success"):
        return result

    files = result["data"].get("files", [])
    if not files:
        return {"success": True, "result": "No files found."}

    formatted_files = []
    for f in files:
        formatted_files.append({
            "id": f.get("id"),
            "name": f.get("name"),
            "type": f.get("mimeType", "").split(".")[-1] if "." in f.get("mimeType", "") else f.get("mimeType"),
            "modified": f.get("modifiedTime"),
            "size": f.get("size"),
            "link": f.get("webViewLink")
        })

    return {"success": True, "result": json.dumps(formatted_files, indent=2)}


async def _drive_read_file(token: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Read file content from Google Drive."""
    file_id = params.get("file_id")
    if not file_id:
        return {"success": False, "error": "file_id is required"}

    # First get file metadata
    meta_result = await _make_google_request(
        "GET",
        f"{DRIVE_API}/files/{file_id}",
        token,
        params={"fields": "id, name, mimeType"}
    )

    if not meta_result.get("success"):
        return meta_result

    mime_type = meta_result["data"].get("mimeType", "")
    file_name = meta_result["data"].get("name", "")

    # Handle Google Docs/Sheets/Slides - export as text
    export_mime = None
    if "document" in mime_type:
        export_mime = "text/plain"
    elif "spreadsheet" in mime_type:
        export_mime = "text/csv"
    elif "presentation" in mime_type:
        export_mime = "text/plain"

    if export_mime:
        result = await _make_google_request(
            "GET",
            f"{DRIVE_API}/files/{file_id}/export",
            token,
            params={"mimeType": export_mime}
        )
    else:
        # Regular file - download content
        result = await _make_google_request(
            "GET",
            f"{DRIVE_API}/files/{file_id}?alt=media",
            token
        )

    if result.get("success"):
        content = result["data"]
        if isinstance(content, dict):
            content = json.dumps(content, indent=2)
        return {"success": True, "result": f"File: {file_name}\n\nContent:\n{content[:10000]}"}
    return result


async def _drive_search_files(token: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Search for files in Google Drive."""
    search_term = params.get("search_term", "")
    file_type = params.get("file_type")
    max_results = min(params.get("max_results", 10), 100)

    if not search_term:
        return {"success": False, "error": "search_term is required"}

    # Build query
    q_parts = [f"(name contains '{search_term}' or fullText contains '{search_term}')"]
    q_parts.append("trashed = false")

    # File type mapping
    type_map = {
        "document": "application/vnd.google-apps.document",
        "spreadsheet": "application/vnd.google-apps.spreadsheet",
        "presentation": "application/vnd.google-apps.presentation",
        "pdf": "application/pdf",
        "image": "mimeType contains 'image/'",
        "folder": "application/vnd.google-apps.folder"
    }

    if file_type and file_type in type_map:
        if file_type == "image":
            q_parts.append(type_map[file_type])
        else:
            q_parts.append(f"mimeType = '{type_map[file_type]}'")

    result = await _make_google_request(
        "GET",
        f"{DRIVE_API}/files",
        token,
        params={
            "q": " and ".join(q_parts),
            "pageSize": max_results,
            "fields": "files(id, name, mimeType, modifiedTime, webViewLink)",
            "orderBy": "modifiedTime desc"
        }
    )

    if not result.get("success"):
        return result

    files = result["data"].get("files", [])
    if not files:
        return {"success": True, "result": f"No files found matching '{search_term}'."}

    formatted_files = []
    for f in files:
        formatted_files.append({
            "id": f.get("id"),
            "name": f.get("name"),
            "type": f.get("mimeType", "").split(".")[-1] if "." in f.get("mimeType", "") else f.get("mimeType"),
            "modified": f.get("modifiedTime"),
            "link": f.get("webViewLink")
        })

    return {"success": True, "result": json.dumps(formatted_files, indent=2)}


# ============= REGISTRATION =============

def _create_tool_handler(service: str):
    """Create a handler function for a specific service."""
    async def handler(params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # This is called by MCPManager.call_tool for internal tools
        # The tool_name is not passed, so we need to get it from somewhere
        # We'll use a workaround: store the tool name in params
        tool_name = params.pop("_tool_name", None)

        if service == "gmail":
            return await handle_gmail_tool(tool_name, params, context)
        elif service == "google-calendar":
            return await handle_calendar_tool(tool_name, params, context)
        elif service == "google-drive":
            return await handle_drive_tool(tool_name, params, context)

        return {"success": False, "error": f"Unknown service: {service}"}

    return handler


def register_google_workspace_tools(manager: MCPManager) -> None:
    """Register all Google Workspace tools with the MCP manager."""

    # Register Gmail tools
    gmail_tools = get_gmail_tools()
    for tool in gmail_tools:
        async def gmail_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]] = None, t=tool) -> Dict[str, Any]:
            return await handle_gmail_tool(t.name, params, context)
        manager.register_internal_tool(tool, gmail_handler)

    # Register Calendar tools
    calendar_tools = get_calendar_tools()
    for tool in calendar_tools:
        async def calendar_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]] = None, t=tool) -> Dict[str, Any]:
            return await handle_calendar_tool(t.name, params, context)
        manager.register_internal_tool(tool, calendar_handler)

    # Register Drive tools
    drive_tools = get_drive_tools()
    for tool in drive_tools:
        async def drive_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]] = None, t=tool) -> Dict[str, Any]:
            return await handle_drive_tool(t.name, params, context)
        manager.register_internal_tool(tool, drive_handler)

    print(f"[MCP] Registered {len(gmail_tools)} Gmail tools, {len(calendar_tools)} Calendar tools, {len(drive_tools)} Drive tools")
