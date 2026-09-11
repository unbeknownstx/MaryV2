# MaryV2 iOS — 13.4 Phase 3A

Native SwiftUI client for the canonical Mary Core.

Included:
- secure Core URL/token setup
- iOS Keychain credential storage
- Core health check
- creator-surface lifecycle
- native text conversation through `/v1/turn`
- `creator-primary` continuity by default

No provider API keys are embedded and no second Mary runtime is created.

## Generate project

```bash
brew install xcodegen
cd ios/MaryV2iOS
xcodegen generate
open MaryV2iOS.xcodeproj
```

## CLI build

```bash
xcodebuild -project MaryV2iOS.xcodeproj -scheme MaryV2iOS -sdk iphonesimulator -configuration Debug CODE_SIGNING_ALLOWED=NO build
```
