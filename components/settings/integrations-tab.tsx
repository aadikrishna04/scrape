"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Github,
  Mail,
  HardDrive,
  Globe,
  Loader2,
  ExternalLink,
  Key,
  Eye,
  EyeOff,
  Circle,
  Zap,
  Database,
  Calendar,
  CreditCard,
  MessageCircle,
  Cloud,
  Phone,
  Table,
  CheckSquare,
  Layout,
  Server,
  LayoutList,
  Search,
  LucideIcon,
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
} from "lucide-react";
import { api, IntegrationStatus, IntegrationRequirements } from "@/lib/api";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

// Icon mapping for integrations
const ICON_MAP: Record<string, LucideIcon> = {
  globe: Globe,
  github: Github,
  mail: Mail,
  folder: HardDrive,
  database: Database,
  calendar: Calendar,
  "credit-card": CreditCard,
  "message-circle": MessageCircle,
  cloud: Cloud,
  phone: Phone,
  table: Table,
  "check-square": CheckSquare,
  layout: Layout,
  server: Server,
  "layout-list": LayoutList,
  search: Search,
  zap: Zap,
  slack: MessageCircle,
  notion: Layout,
  linear: LayoutList,
  jira: CheckSquare,
  trello: Table,
};

// Integration metadata for UI display (capabilities, etc.)
const INTEGRATION_META: Record<string, { capabilities: string[] }> = {
  browser: { capabilities: ["Web scraping", "Form filling", "Screenshots", "Click automation"] },
  scrape: { capabilities: ["Static sites", "Pagination", "AI extraction"] },
  ai: { capabilities: ["Process data", "Summarize", "Extract info", "Generate content"] },
  github: { capabilities: ["Create issues", "Manage PRs", "Access repos", "Search code"] },
  filesystem: { capabilities: ["Read files", "Write files", "List directories"] },
  notion: { capabilities: ["Create pages", "Query databases", "Update content"] },
  linear: { capabilities: ["Create issues", "Manage projects", "Query teams"] },
  jira: { capabilities: ["Create issues", "Manage boards", "Add comments"] },
  trello: { capabilities: ["Create cards", "Move cards", "Manage lists"] },
  airtable: { capabilities: ["Query records", "Create records", "Read schemas"] },
  slack: { capabilities: ["Send messages", "Read channels", "Search"] },
  discord: { capabilities: ["Send messages", "Read channels", "Manage server"] },
  gmail: { capabilities: ["Send emails", "Read inbox", "Manage labels"] },
  sendgrid: { capabilities: ["Send emails", "Use templates", "View analytics"] },
  twilio: { capabilities: ["Send SMS", "Make calls", "Manage numbers"] },
  "google-calendar": { capabilities: ["Create events", "Read events", "Check availability"] },
  postgres: { capabilities: ["Run queries", "Read schema", "CRUD operations"] },
  mongodb: { capabilities: ["CRUD operations", "Aggregation", "Indexes"] },
  redis: { capabilities: ["Key-value ops", "Pub/sub", "Caching"] },
  "google-drive": { capabilities: ["Read files", "Upload files", "Share files"] },
  stripe: { capabilities: ["Create charges", "Manage customers", "View transactions"] },
  aws: { capabilities: ["S3 operations", "Lambda invoke", "SES email"] },
  "brave-search": { capabilities: ["Web search", "News search", "Image search"] },
};

// Google OAuth services - all use our internal OAuth flow
const GOOGLE_SERVICES = ["gmail", "google-calendar", "google-drive"];

export default function IntegrationsTab() {
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState<string | null>(null);

  // Token dialog state
  const [tokenDialogOpen, setTokenDialogOpen] = useState(false);
  const [tokenDialogProvider, setTokenDialogProvider] = useState<string | null>(null);
  const [tokenRequirements, setTokenRequirements] = useState<IntegrationRequirements | null>(null);
  const [tokenValue, setTokenValue] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [copiedStep, setCopiedStep] = useState<number | null>(null);

  useEffect(() => {
    loadIntegrations();
  }, []);

  // Handle OAuth callback redirect
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);

      // GitHub callback
      if (params.get("github") === "connected") {
        toast.success("GitHub connected successfully!");
        loadIntegrations();
        window.history.replaceState({}, "", window.location.pathname);
      }

      // Google callback
      const googleService = params.get("google");
      if (googleService && params.get("connected") === "true") {
        const serviceName = googleService === "gmail" ? "Gmail" :
          googleService === "google-calendar" ? "Google Calendar" : "Google Drive";
        toast.success(`${serviceName} connected successfully!`);
        loadIntegrations();
        window.history.replaceState({}, "", window.location.pathname);
      }

      // Google error
      const googleError = params.get("google_error");
      if (googleError) {
        toast.error(`Google connection failed: ${googleError}`);
        window.history.replaceState({}, "", window.location.pathname);
      }
    }
  }, []);

  const loadIntegrations = async () => {
    try {
      const data = await api.integrations.list();
      setIntegrations(data.integrations);
    } catch (error) {
      console.error("Failed to load integrations:", error);
      toast.error("Failed to load integrations");
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async (integration: IntegrationStatus) => {
    // Handle GitHub OAuth
    if (integration.name === "github") {
      setConnecting(integration.name);
      try {
        const { url } = await api.integrations.getGithubOAuthStart();
        window.location.href = url;
      } catch (error: any) {
        toast.error(error?.message || "Failed to start GitHub OAuth");
        setConnecting(null);
      }
      return;
    }

    // Handle Google OAuth services
    if (GOOGLE_SERVICES.includes(integration.name)) {
      setConnecting(integration.name);
      try {
        const { url } = await api.integrations.getGoogleOAuthStart(
          integration.name as 'gmail' | 'google-calendar' | 'google-drive'
        );
        window.location.href = url;
      } catch (error: any) {
        toast.error(error?.message || "Failed to start Google OAuth");
        setConnecting(null);
      }
      return;
    }

    // Handle token-based integrations
    if (integration.auth_type === "token") {
      try {
        const requirements = await api.integrations.getRequirements(integration.name);
        setTokenDialogProvider(integration.name);
        setTokenRequirements(requirements);
        setTokenValue("");
        setShowToken(false);
        setTokenDialogOpen(true);
      } catch (error: any) {
        toast.error(error?.message || "Failed to get integration requirements");
      }
      return;
    }

    // No auth needed
    toast.info(`${integration.display_name} doesn't require authentication.`);
  };

  const handleTokenSubmit = async () => {
    if (!tokenDialogProvider || !tokenValue.trim()) {
      toast.error("Please enter a token");
      return;
    }

    setConnecting(tokenDialogProvider);
    try {
      const result = await api.integrations.connect(tokenDialogProvider, tokenValue.trim());

      if (result.warning) {
        toast.warning(result.warning);
      } else {
        const info = (result as any).info;
        toast.success(info || `Connected to ${tokenRequirements?.name || tokenDialogProvider}`);
      }

      setTokenDialogOpen(false);
      setTokenValue("");
      await loadIntegrations();
    } catch (error: any) {
      toast.error(error?.message || "Failed to connect");
    } finally {
      setConnecting(null);
    }
  };

  const handleDisconnect = async (integration: IntegrationStatus) => {
    if (integration.auth_type === "none") {
      toast.info("This integration cannot be disconnected.");
      return;
    }

    setConnecting(integration.name);
    try {
      // Use specific disconnect for Google services
      if (GOOGLE_SERVICES.includes(integration.name)) {
        await api.integrations.disconnectGoogle(integration.name);
      } else {
        await api.integrations.disconnect(integration.name);
      }
      toast.success(`Disconnected from ${integration.display_name}`);
      await loadIntegrations();
    } catch (error: any) {
      toast.error(error?.message || "Failed to disconnect");
    } finally {
      setConnecting(null);
    }
  };

  const copyToClipboard = (text: string, stepIndex: number) => {
    navigator.clipboard.writeText(text);
    setCopiedStep(stepIndex);
    setTimeout(() => setCopiedStep(null), 2000);
  };

  const getIcon = (integration: IntegrationStatus) => {
    const IconComponent = ICON_MAP[integration.icon || ""] || ICON_MAP[integration.name] || Globe;
    return <IconComponent className="w-5 h-5" />;
  };

  const getCapabilities = (name: string): string[] => {
    return INTEGRATION_META[name]?.capabilities || [];
  };

  // Group integrations by category
  const groupedIntegrations = {
    core: integrations.filter(i => ["browser", "scrape", "ai", "github", "filesystem"].includes(i.name)),
    productivity: integrations.filter(i => ["notion", "linear", "jira", "trello", "airtable"].includes(i.name)),
    communication: integrations.filter(i => ["slack", "discord", "gmail", "sendgrid", "twilio", "google-calendar"].includes(i.name)),
    data: integrations.filter(i => ["postgres", "mongodb", "redis", "google-drive"].includes(i.name)),
    cloud: integrations.filter(i => ["aws", "stripe", "brave-search"].includes(i.name)),
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const renderIntegrationGroup = (title: string, items: IntegrationStatus[]) => {
    if (items.length === 0) return null;

    return (
      <Card key={title}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">{title}</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y divide-border">
            {items.map((integration) => {
              const isLoading = connecting === integration.name;
              const capabilities = getCapabilities(integration.name);
              const isOAuth = integration.name === "github" || GOOGLE_SERVICES.includes(integration.name);

              return (
                <div
                  key={integration.name}
                  className="flex items-center gap-4 p-4 transition-colors hover:bg-muted/50"
                >
                  <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center shrink-0">
                    {getIcon(integration)}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-sm text-foreground">
                        {integration.display_name}
                      </p>
                      {isOAuth && (
                        <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                          OAuth
                        </span>
                      )}
                    </div>
                    {integration.description && (
                      <p className="text-sm text-muted-foreground truncate">
                        {integration.description}
                      </p>
                    )}
                    {capabilities.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {capabilities.map((cap) => (
                          <span
                            key={cap}
                            className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded"
                          >
                            {cap}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <div className="flex items-center gap-2">
                      <Circle
                        className={cn(
                          "w-2 h-2",
                          integration.connected
                            ? "fill-emerald-500 text-emerald-500"
                            : "fill-muted-foreground/30 text-muted-foreground/30"
                        )}
                      />
                      <span className="text-xs text-muted-foreground hidden sm:inline">
                        {integration.connected ? "Connected" : "Not connected"}
                      </span>
                    </div>

                    {integration.auth_type !== "none" && (
                      <Button
                        variant={integration.connected ? "outline" : "default"}
                        size="sm"
                        onClick={() =>
                          integration.connected
                            ? handleDisconnect(integration)
                            : handleConnect(integration)
                        }
                        disabled={isLoading}
                        className="min-w-[90px]"
                      >
                        {isLoading ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : integration.connected ? (
                          "Disconnect"
                        ) : (
                          "Connect"
                        )}
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="space-y-6">
      {renderIntegrationGroup("Core", groupedIntegrations.core)}
      {renderIntegrationGroup("Productivity", groupedIntegrations.productivity)}
      {renderIntegrationGroup("Communication", groupedIntegrations.communication)}
      {renderIntegrationGroup("Data & Storage", groupedIntegrations.data)}
      {renderIntegrationGroup("Cloud & Services", groupedIntegrations.cloud)}

      <Card className="border-dashed">
        <CardContent className="flex flex-col items-center justify-center py-10 text-center">
          <div className="w-11 h-11 rounded-xl bg-muted flex items-center justify-center mb-4">
            <CheckCircle2 className="w-5 h-5 text-muted-foreground" />
          </div>
          <p className="font-medium text-foreground mb-1">
            {integrations.filter(i => i.connected).length} of {integrations.length} integrations connected
          </p>
          <p className="text-sm text-muted-foreground max-w-sm">
            Your tokens are stored securely per-user. Connect once and use across all workflows.
          </p>
        </CardContent>
      </Card>

      {/* Token Dialog */}
      <Dialog open={tokenDialogOpen} onOpenChange={setTokenDialogOpen}>
        <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Key className="w-5 h-5" />
              Connect {tokenRequirements?.name || tokenDialogProvider}
            </DialogTitle>
            <DialogDescription>
              {tokenRequirements?.description}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Required Scopes */}
            {tokenRequirements?.required_scopes && tokenRequirements.required_scopes.length > 0 && (
              <div className="rounded-lg bg-amber-50 border border-amber-200 p-3">
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-amber-800">Required Permissions</p>
                    <p className="text-xs text-amber-700 mt-1">
                      Make sure your token has these scopes enabled:
                    </p>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {tokenRequirements.required_scopes.map((scope) => (
                        <span
                          key={scope}
                          className="text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded font-mono"
                        >
                          {scope}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Setup Steps */}
            {tokenRequirements?.setup_steps && tokenRequirements.setup_steps.length > 0 && (
              <Accordion type="single" collapsible className="w-full">
                <AccordionItem value="steps" className="border rounded-lg">
                  <AccordionTrigger className="px-3 py-2 text-sm hover:no-underline">
                    <span className="flex items-center gap-2">
                      <ExternalLink className="w-4 h-4" />
                      Setup Instructions ({tokenRequirements.setup_steps.length} steps)
                    </span>
                  </AccordionTrigger>
                  <AccordionContent className="px-3 pb-3">
                    <ol className="space-y-2 text-sm">
                      {tokenRequirements.setup_steps.map((step, index) => (
                        <li key={index} className="flex items-start gap-2">
                          <span className="flex items-center justify-center w-5 h-5 rounded-full bg-muted text-xs font-medium shrink-0 mt-0.5">
                            {index + 1}
                          </span>
                          <span className="text-muted-foreground">{step}</span>
                        </li>
                      ))}
                    </ol>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            )}

            {/* Token Input */}
            <div className="space-y-2">
              <Label htmlFor="token">{tokenRequirements?.name || "Token"}</Label>
              <div className="relative">
                <Input
                  id="token"
                  type={showToken ? "text" : "password"}
                  placeholder="Paste your token here..."
                  value={tokenValue}
                  onChange={(e) => setTokenValue(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleTokenSubmit()}
                  className="pr-10 h-11 font-mono text-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowToken(!showToken)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Help Link */}
            {tokenRequirements?.help_url && (
              <a
                href={tokenRequirements.help_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Get your {tokenRequirements?.name?.toLowerCase() || "token"}
              </a>
            )}

            <p className="text-xs text-muted-foreground">
              Your token is validated before saving and stored securely per-user.
            </p>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setTokenDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleTokenSubmit}
              disabled={!tokenValue.trim() || connecting === tokenDialogProvider}
            >
              {connecting === tokenDialogProvider ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : null}
              Connect
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
