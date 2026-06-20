# Mobile app builds

Place mobile app files in this folder so FastAPI can serve them from `/static/apps/`.

- Android APK: `static/apps/potatoscan.apk`
- iOS IPA: `static/apps/potatoscan.ipa`

Android users can download the APK directly from the dashboard. APK files are ignored by git because release builds can exceed GitHub's single-file size limit; copy the release APK to this folder on each deployed server.

iOS normally requires TestFlight, App Store, Apple Configurator, or an enterprise/ad-hoc signed install flow. A raw IPA link is useful for storage or controlled distribution, but most iPhones will not install it directly from a normal browser link.
