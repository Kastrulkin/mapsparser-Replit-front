#!/bin/bash
npm --prefix frontend test -- src/components/telegram/PlatformOutreach.test.tsx src/pages/TelegramControlPage.test.tsx src/components/telegram/JobProgressSheet.test.tsx src/components/telegram/PartnershipsMobileModule.test.tsx > .agent/tasks/localos-miniapp-outreach-20261112/raw/baseline-frontend.log 2>&1
result=$?
printf "%s" "$result" > .agent/tasks/localos-miniapp-outreach-20261112/raw/baseline-frontend.exit
