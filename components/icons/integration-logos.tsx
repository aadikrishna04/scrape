'use client'

import {
  SiGithub,
  SiSlack,
  SiNotion,
  SiLinear,
  SiJira,
  SiTrello,
  SiAirtable,
  SiDiscord,
  SiGmail,
  SiTwilio,
  SiGooglecalendar,
  SiPostgresql,
  SiMongodb,
  SiRedis,
  SiGoogledrive,
  SiStripe,
  SiBrave,
} from '@icons-pack/react-simple-icons'
import { Globe, Zap, FolderOpen, Sparkles, Wrench, Cloud, Mail, Send } from 'lucide-react'

interface LogoProps {
  className?: string
}

// Built-in tool icons (not company brands)
export function BrowserLogo({ className = "w-4 h-4" }: LogoProps) {
  return <Globe className={className} style={{ color: '#60A5FA' }} />
}

export function AILogo({ className = "w-4 h-4" }: LogoProps) {
  return <Sparkles className={className} style={{ color: '#8B5CF6' }} />
}

export function ScrapeLogo({ className = "w-4 h-4" }: LogoProps) {
  return <Zap className={className} style={{ color: '#F59E0B' }} />
}

export function FileSystemLogo({ className = "w-4 h-4" }: LogoProps) {
  return <FolderOpen className={className} style={{ color: '#10B981' }} />
}

// Fallback icons for services without simple-icons
export function AWSLogo({ className = "w-4 h-4" }: LogoProps) {
  return <Cloud className={className} style={{ color: '#FF9900' }} />
}

export function SendGridLogo({ className = "w-4 h-4" }: LogoProps) {
  return <Send className={className} style={{ color: '#1A82E2' }} />
}

// Map integration names to their logo components
export const integrationLogos: Record<string, React.ComponentType<LogoProps>> = {
  // Company brands (using simple-icons)
  github: ({ className }) => <SiGithub className={className} color="#181717" />,
  slack: ({ className }) => <SiSlack className={className} color="#4A154B" />,
  notion: ({ className }) => <SiNotion className={className} color="#000000" />,
  linear: ({ className }) => <SiLinear className={className} color="#5E6AD2" />,
  jira: ({ className }) => <SiJira className={className} color="#0052CC" />,
  trello: ({ className }) => <SiTrello className={className} color="#0052CC" />,
  airtable: ({ className }) => <SiAirtable className={className} color="#18BFFF" />,
  discord: ({ className }) => <SiDiscord className={className} color="#5865F2" />,
  gmail: ({ className }) => <SiGmail className={className} color="#EA4335" />,
  twilio: ({ className }) => <SiTwilio className={className} color="#F22F46" />,
  'google-calendar': ({ className }) => <SiGooglecalendar className={className} color="#4285F4" />,
  postgres: ({ className }) => <SiPostgresql className={className} color="#4169E1" />,
  mongodb: ({ className }) => <SiMongodb className={className} color="#47A248" />,
  redis: ({ className }) => <SiRedis className={className} color="#DC382D" />,
  'google-drive': ({ className }) => <SiGoogledrive className={className} color="#4285F4" />,
  stripe: ({ className }) => <SiStripe className={className} color="#635BFF" />,
  'brave-search': ({ className }) => <SiBrave className={className} color="#FB542B" />,

  // Fallback icons for services without simple-icons
  aws: AWSLogo,
  sendgrid: SendGridLogo,

  // Built-in tools
  browser: BrowserLogo,
  ai: AILogo,
  scrape: ScrapeLogo,
  filesystem: FileSystemLogo,
}

// Default fallback icon
export function DefaultLogo({ className = "w-4 h-4" }: LogoProps) {
  return <Wrench className={className} style={{ color: '#6B7280' }} />
}
