# Encontra.ai

[![CI](https://github.com/HanuBehr/encontraaiapp/actions/workflows/ci.yml/badge.svg)](https://github.com/HanuBehr/encontraaiapp/actions/workflows/ci.yml)
[![Live demo](https://img.shields.io/badge/Live_demo-open-6d28d9?style=for-the-badge)](https://encontraaiapp.vercel.app)

B2B prospecting is not slow because sales teams cannot sell. It is slow because the lead list is usually garbage.

Encontra.ai turns a market search into a reviewed lead list without pretending provider data is clean.

It handles discovery, duplicate prevention, contact enrichment, company-record evidence scoring, manual review, assignment rules and CRM-ready Excel exports.

[Open the live demo](https://encontraaiapp.vercel.app) · Fictional data, no login or API keys required.

![Encontra.ai discovery workspace](web/public/brand/encontra-macos-readme-window.png)

## Why I built it

I kept seeing sales work begin with the same mess: provider searches copied into spreadsheets, duplicates mixed with useful companies, missing contact details and records nobody could confidently verify.

Encontra.ai started as a way to remove that manual cleanup without hiding uncertainty behind automation. When the system cannot confidently match, merge or classify something, it keeps the evidence and sends the decision to review.

## How it works

```text
Market search -> Preview -> Import -> Dedupe -> Enrichment -> Company review -> Assignment -> Export
