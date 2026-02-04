'use client'

import { useState } from 'react'
import DashboardLayout from '@/components/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Plug, User, Bell, Shield } from 'lucide-react'
import IntegrationsTab from '@/components/settings/integrations-tab'
import { cn } from '@/lib/utils'

const tabs = [
  { id: 'integrations', label: 'Integrations', icon: Plug },
  { id: 'profile', label: 'Profile', icon: User },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'security', label: 'Security', icon: Shield },
]

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('integrations')

  return (
    <DashboardLayout>
      <div className="flex-1 overflow-auto">
        <div className="max-w-4xl mx-auto px-6 py-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-2xl font-semibold text-foreground">Settings</h1>
            <p className="text-muted-foreground mt-1">
              Manage your account and preferences
            </p>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 p-1 bg-muted rounded-lg w-fit mb-8">
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-all",
                    activeTab === tab.id
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon className="w-4 h-4" />
                  <span className="hidden sm:inline">{tab.label}</span>
                </button>
              )
            })}
          </div>

          {/* Content */}
          <div className="space-y-6">
            {activeTab === 'integrations' && <IntegrationsTab />}

            {activeTab === 'profile' && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Profile</CardTitle>
                  <CardDescription>
                    Manage your account information
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid gap-6 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="name">Display Name</Label>
                      <Input id="name" placeholder="Your name" className="h-11" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">Email</Label>
                      <Input
                        id="email"
                        type="email"
                        placeholder="you@example.com"
                        disabled
                        className="h-11"
                      />
                      <p className="text-xs text-muted-foreground">
                        Email cannot be changed
                      </p>
                    </div>
                  </div>
                  <Button>Save Changes</Button>
                </CardContent>
              </Card>
            )}

            {activeTab === 'notifications' && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Notifications</CardTitle>
                  <CardDescription>
                    Configure how you receive updates
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex items-center justify-between py-3">
                    <div className="space-y-0.5">
                      <Label className="text-sm font-medium">Workflow Completion</Label>
                      <p className="text-sm text-muted-foreground">
                        Get notified when workflows finish executing
                      </p>
                    </div>
                    <Switch defaultChecked />
                  </div>
                  <div className="border-t border-border" />
                  <div className="flex items-center justify-between py-3">
                    <div className="space-y-0.5">
                      <Label className="text-sm font-medium">Error Alerts</Label>
                      <p className="text-sm text-muted-foreground">
                        Get notified when workflows encounter errors
                      </p>
                    </div>
                    <Switch defaultChecked />
                  </div>
                  <div className="border-t border-border" />
                  <div className="flex items-center justify-between py-3">
                    <div className="space-y-0.5">
                      <Label className="text-sm font-medium">Weekly Summary</Label>
                      <p className="text-sm text-muted-foreground">
                        Receive a weekly summary of your activity
                      </p>
                    </div>
                    <Switch />
                  </div>
                </CardContent>
              </Card>
            )}

            {activeTab === 'security' && (
              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Password</CardTitle>
                    <CardDescription>
                      Change your account password
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="current">Current Password</Label>
                        <Input id="current" type="password" className="h-11" />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="new">New Password</Label>
                        <Input id="new" type="password" className="h-11" />
                      </div>
                    </div>
                    <Button variant="outline">Update Password</Button>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Two-Factor Authentication</CardTitle>
                    <CardDescription>
                      Add an extra layer of security
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <p className="text-sm font-medium">Status</p>
                        <p className="text-sm text-muted-foreground">
                          2FA is currently disabled
                        </p>
                      </div>
                      <Button variant="outline">Enable 2FA</Button>
                    </div>
                  </CardContent>
                </Card>

                <Card className="border-destructive/20">
                  <CardHeader>
                    <CardTitle className="text-lg text-destructive">Danger Zone</CardTitle>
                    <CardDescription>
                      Permanently delete your account and all data
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Button variant="destructive">Delete Account</Button>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
