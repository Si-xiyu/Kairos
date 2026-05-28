# Kairos Context

## Personal Assistant

Kairos is a local-first assistant that can hold conversations with the user, remember useful preferences, run approved tools, and proactively surface reminders.

## Agent Loop

The agent loop is the turn-by-turn runtime that records user messages, asks a model or local fallback for a response, executes permitted tools, and stores the resulting session events.

## Tool

A tool is an action Kairos can call through the shared permission and audit pipeline.

## MCP Tool

An MCP tool is a tool exposed by a configured external MCP server and made available to Kairos through the same permission and audit pipeline as native tools.

## Heartbeat

Heartbeat is Kairos's proactive check for whether it should stay silent or create a reminder. If no action is needed, the canonical result is `HEARTBEAT_OK`.

## Delivery Queue

The delivery queue is the durable local queue for outbound messages and notifications, including retry and failed-delivery tracking.

## Windows Notification

A Windows notification is a local desktop notification used by Kairos to surface a reminder without requiring the main chat window to be open.
