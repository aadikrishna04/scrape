'use client'

import { useState } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { JSONSchema } from '@/lib/types/mcp'

interface DynamicParamsFormProps {
  schema: JSONSchema
  values: Record<string, unknown>
  onChange: (values: Record<string, unknown>) => void
  disabled?: boolean
  /** When set, show "Use my GitHub username" for the owner param (GitHub repo tools). */
  onFetchGithubLogin?: () => Promise<string | null>
}

interface FormFieldProps {
  name: string
  schema: JSONSchema
  required: boolean
  value: unknown
  onChange: (value: unknown) => void
  disabled?: boolean
  onUseGithubLogin?: () => void
}

function OwnerFieldHelper({ onUseGithubLogin }: { onUseGithubLogin: () => void | Promise<void> }) {
  const [loading, setLoading] = useState(false)
  const handleClick = async () => {
    setLoading(true)
    try {
      await onUseGithubLogin()
    } finally {
      setLoading(false)
    }
  }
  return (
    <div className="pt-1 space-y-1.5">
      <p className="text-xs text-muted-foreground">
        Your GitHub username or the organization that owns the repo (first part of <code className="text-[10px]">github.com/OWNER/repo-name</code>).
      </p>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-7 text-xs"
        onClick={handleClick}
        disabled={loading}
      >
        {loading ? 'Loading…' : 'Use my GitHub username'}
      </Button>
    </div>
  )
}

function FormField({ name, schema, required, value, onChange, disabled, onUseGithubLogin }: FormFieldProps) {
  const type = schema.type
  const label = name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
  const description = schema.description
  const isOwnerField = name === 'owner'

  // Render based on type
  if (schema.enum) {
    return (
      <div className="space-y-2">
        <Label htmlFor={name}>
          {label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </Label>
        <Select
          value={value as string || ''}
          onValueChange={onChange}
          disabled={disabled}
        >
          <SelectTrigger id={name}>
            <SelectValue placeholder={`Select ${label.toLowerCase()}`} />
          </SelectTrigger>
          <SelectContent>
            {schema.enum.map((option) => (
              <SelectItem key={option} value={option}>
                {option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
    )
  }

  switch (type) {
    case 'string':
      // Use textarea for longer descriptions or if it looks like content
      const isLongText = name.includes('description') || name.includes('instruction') || name.includes('content') || name.includes('body')
      if (isLongText) {
        return (
          <div className="space-y-2">
            <Label htmlFor={name}>
              {label}
              {required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Textarea
              id={name}
              value={value as string || ''}
              onChange={(e) => onChange(e.target.value)}
              placeholder={description || `Enter ${label.toLowerCase()}`}
              rows={3}
              disabled={disabled}
            />
            {description && <p className="text-xs text-muted-foreground">{description}</p>}
          </div>
        )
      }
      return (
        <div className="space-y-2">
          <Label htmlFor={name}>
            {label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </Label>
          <Input
            id={name}
            type="text"
            value={value as string || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={description || `Enter ${label.toLowerCase()}`}
            disabled={disabled}
          />
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
          {isOwnerField && onUseGithubLogin && (
            <OwnerFieldHelper onUseGithubLogin={onUseGithubLogin} />
          )}
        </div>
      )

    case 'number':
    case 'integer':
      return (
        <div className="space-y-2">
          <Label htmlFor={name}>
            {label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </Label>
          <Input
            id={name}
            type="number"
            value={value as number ?? ''}
            onChange={(e) => onChange(e.target.value ? Number(e.target.value) : undefined)}
            placeholder={description || `Enter ${label.toLowerCase()}`}
            disabled={disabled}
          />
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
      )

    case 'boolean':
      return (
        <div className="flex items-center space-x-2">
          <Checkbox
            id={name}
            checked={value as boolean || false}
            onCheckedChange={onChange}
            disabled={disabled}
          />
          <div>
            <Label htmlFor={name} className="cursor-pointer">
              {label}
              {required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            {description && <p className="text-xs text-muted-foreground">{description}</p>}
          </div>
        </div>
      )

    case 'object':
      // Render nested object as a JSON textarea for now
      return (
        <div className="space-y-2">
          <Label htmlFor={name}>
            {label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </Label>
          <Textarea
            id={name}
            value={typeof value === 'object' ? JSON.stringify(value, null, 2) : '{}'}
            onChange={(e) => {
              try {
                onChange(JSON.parse(e.target.value))
              } catch {
                // Keep the text but don't update the parsed value
              }
            }}
            placeholder="{ }"
            rows={4}
            className="font-mono text-sm"
            disabled={disabled}
          />
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
      )

    case 'array':
      // Render array as a JSON textarea for now
      return (
        <div className="space-y-2">
          <Label htmlFor={name}>
            {label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </Label>
          <Textarea
            id={name}
            value={Array.isArray(value) ? JSON.stringify(value, null, 2) : '[]'}
            onChange={(e) => {
              try {
                onChange(JSON.parse(e.target.value))
              } catch {
                // Keep the text but don't update the parsed value
              }
            }}
            placeholder="[ ]"
            rows={3}
            className="font-mono text-sm"
            disabled={disabled}
          />
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
      )

    default:
      // Fallback to text input
      return (
        <div className="space-y-2">
          <Label htmlFor={name}>
            {label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </Label>
          <Input
            id={name}
            type="text"
            value={String(value || '')}
            onChange={(e) => onChange(e.target.value)}
            placeholder={description || `Enter ${label.toLowerCase()}`}
            disabled={disabled}
          />
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
      )
  }
}

export default function DynamicParamsForm({ schema, values, onChange, disabled, onFetchGithubLogin }: DynamicParamsFormProps) {
  const properties = schema.properties || {}
  const required = new Set(schema.required || [])

  // Sort properties: required first, then alphabetically
  const sortedKeys = Object.keys(properties).sort((a, b) => {
    const aRequired = required.has(a)
    const bRequired = required.has(b)
    if (aRequired && !bRequired) return -1
    if (!aRequired && bRequired) return 1
    return a.localeCompare(b)
  })

  if (sortedKeys.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">
        No parameters required for this tool.
      </p>
    )
  }

  return (
    <div className="space-y-4">
      {sortedKeys.map((name) => (
        <FormField
          key={name}
          name={name}
          schema={properties[name]}
          required={required.has(name)}
          value={values[name]}
          onChange={(value) => onChange({ ...values, [name]: value })}
          disabled={disabled}
          onUseGithubLogin={
            name === 'owner' && onFetchGithubLogin
              ? async () => {
                  const login = await onFetchGithubLogin()
                  if (login) onChange({ ...values, owner: login })
                }
              : undefined
          }
        />
      ))}
    </div>
  )
}
