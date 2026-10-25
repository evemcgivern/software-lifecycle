---
title: OpenAI API Models
addedAt: 2026-09-05
category: service
tags: llm
iconSlug: openai
permalink: /openai-api-models
alternate_urls:
  - /openai
releasePolicyLink: https://developers.openai.com/api/docs/deprecations
latestColumn: false
eoasColumn: Active support
eolColumn: Deprecated support
staleReleaseThresholdDays: 1095 # llm may have longer support periods

customFields:
  - name: aliases
    display: api-only
    label: Aliases
    description: Alternative names for the OpenAI model
  - name: recommendedReplacement
    display: after-latest-column
    label: Recommended replacement
    description: Recommended replacement from OpenAI's model deprecation notices
    link: https://developers.openai.com/api/docs/deprecations

auto:
  methods:
    - openai_models: https://developers.openai.com/api/docs/models/all
    - openai_deprecations: https://developers.openai.com/api/docs/deprecations

releases:
  - releaseCycle: "gpt-6.1-sol"
    releaseLabel: "GPT-6.1 Sol"
    aliases:
      - gpt-6.1-sol
      - gpt-6.1-sol
    releaseDate: 2026-09-29 # https://openai.com/index/introducing-gpt-6-1-sol/
    eoas: false
    eol: false
    link: "https://developers.openai.com/api/docs/models/gpt-6.1-sol"

  - releaseCycle: "gpt-6-sol"
    releaseLabel: "GPT-6 Sol"
    aliases:
      - gpt-6-sol
      - gpt-6-sol
    releaseDate: 2026-09-22 # https://openai.com/index/introducing-gpt-6-sol-and-luna/
    eoas: false
    eol: false
    link: "https://developers.openai.com/api/docs/models/gpt-6-sol"
    recommendedReplacement: N/A

---

Description text removed from this test copy.
