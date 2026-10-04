# App Store Connect Screenshot Reset

A Python utility for inspecting and removing screenshot sets that are stuck processing in App Store Connect and blocking submission for review.

**Created by [Mohamad Masri](https://apps.apple.com/developer/mohammad-masri/id975614455), independent iOS developer.**

I created this tool after encountering stuck screenshot uploads while updating my own app. The workaround successfully resolved the issue for me, so I’m sharing it to help other developers facing the same problem.

**[Explore my apps on the App Store →](https://apps.apple.com/developer/mohammad-masri/id975614455)**

## The problem

Screenshots can remain as pink placeholders or loading indicators in App Store Connect. The delete button may be missing, **Delete All** may be disabled, and submitting for review may produce:

> There are still screenshot uploads in progress.

This tool uses Apple’s official App Store Connect API to inspect the affected screenshots and delete selected screenshot sets, allowing you to upload your images again through App Store Connect.

Related discussion: [Apple Developer Forums — Screenshot upload stuck on processing](https://developer.apple.com/forums/thread/848464).

## What it does

- Lists screenshot sets, filenames, asset IDs, processing states, and available processing errors.
- Runs in **inspection-only mode by default**.
- Lets you select individual sets or all sets for one app version and language.
- Requires an explicit typed confirmation before deletion.
- Restricts operation to iOS versions in **Prepare for Submission**.
- Rechecks the version state and selected screenshot membership before starting deletion.
- Saves a local JSON metadata report and records successful deletions.
- Checks whether the selected sets are still present after deletion.

**Deletion removes every image in a selected set, including images that uploaded successfully. Keep your original files for reuploading. The JSON report is not an image backup.**

## Requirements

- Python **3.9 or later**.
- The `PyJWT[crypto]` package.
- An App Store Connect **Team API key** with permission to manage the app’s screenshots, such as the **App Manager** role.
- Your **Key ID**, **Issuer ID**, and downloaded `.p8` private key.
- Your app’s numeric **Apple ID**, available in App Store Connect under **App Information**.
- An iOS version in **Prepare for Submission**.

The setup commands below are for macOS. This script currently uses Team API key authentication; individual API keys are not supported.

## 1. Create an App Store Connect API key

1. Sign in to [App Store Connect](https://appstoreconnect.apple.com/).
2. Go to **Users and Access → Integrations → App Store Connect API**.
3. If API access is not enabled, use the **Account Holder** account to request access.
4. Under **Team Keys**, select **Generate API Key** or the **+** button.
5. Give the key a recognizable name, such as `Screenshot Reset`, and select **App Manager** access.
6. Generate the key and download its `.p8` file.
7. Note the **Key ID** and **Issuer ID**. The Issuer ID is different from your Apple Developer Team ID.

Keep the private key outside your repository. Do not commit it to GitHub or include it in issue reports. The script reads the key locally and sends signed authentication tokens to Apple’s API; it does not upload the `.p8` file.

Apple’s guide: [Creating API Keys for App Store Connect API](https://developer.apple.com/documentation/appstoreconnectapi/creating-api-keys-for-app-store-connect-api).

## 2. Install

Download or clone this repository, open Terminal in the folder containing `asc_screenshot_reset.py`, and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'PyJWT[crypto]'
```

In a new Terminal session, return to the same folder and run `source .venv/bin/activate` before using the script.

## 3. Inspect your screenshots

```bash
python asc_screenshot_reset.py
```

The script prompts for the following:

| Prompt | What to enter |
| --- | --- |
| `.p8` file path | The path to your downloaded key, such as `/Users/you/Keys/AuthKey_ABC123.p8` |
| Key ID | The identifier shown beside your API key |
| Issuer ID | The issuer identifier from the Team Keys page |
| Apple ID | Your app’s numeric Apple ID, not its bundle identifier |
| iOS version | The exact version you are preparing to submit |
| Locale | The language code for the affected screenshots, such as `en-US` |

The current script defaults to version **`2.0`** and locale **`en-US`**, and its Apple ID prompt mentions **Classic Pop It**, the app for which it was originally created. **Enter your own app’s Apple ID, version, and locale.** The app name in the prompt does not restrict which app you can use.

Review the displayed app name, bundle identifier, version, language, and numbered screenshot sets. This command makes no changes.

## 4. Delete the affected sets

Once you have identified the correct sets and have your original screenshot files ready, run:

```bash
python asc_screenshot_reset.py --delete
```

When asked which sets to delete, enter:

- `1` to delete set 1.
- `1,3` to delete sets 1 and 3.
- `all` to delete all listed sets for the selected app version and locale, including any iPad sets listed.

The selection applies to **whole screenshot sets**, not individual images. Other languages require a separate run with their locale code.

The script displays your selection and asks you to type an exact confirmation containing your app ID, version, and locale. For example:

```text
DELETE 1234567890 2.0 en-US
```

Use the exact phrase displayed for your app. Any other response cancels deletion.

A report named `asc-screenshot-reset-<app-id>-<timestamp>.json` is saved in the current folder before deletion begins and updated after each successful deletion.

## 5. Upload your screenshots again

1. Refresh your app version in App Store Connect.
2. Upload one screenshot to the affected display size.
3. Wait for processing to complete before uploading the remaining screenshots.
4. Check the required device sizes and languages, then try submitting for review again.

Reuploading is done manually in App Store Connect. The script does not upload images or submit your app for review.

## Troubleshooting

| Message or symptom | What to check |
| --- | --- |
| `No module named 'jwt'` or a dependency error | Activate the virtual environment and run `python -m pip install 'PyJWT[crypto]'`. |
| Key file not found | Enter the actual path to the `.p8` file. You can use a path beginning with `~/`. |
| HTTP `401` | Check the Key ID, Issuer ID, matching Team private key, and your Mac’s date and time. |
| HTTP `403` | Check that the key’s role allows the operation and that you are using the correct App Store Connect account. |
| Version or locale not found | Enter the exact iOS version and locale. Available locales are listed when a locale cannot be matched. |
| Version is not in Prepare for Submission | The script intentionally stops for other version states. |
| Screenshot membership changed | Run inspection again, review the updated sets, and retry your selection. |
| An error occurs during deletion | Some earlier sets may already have been deleted. Run inspection again before retrying. |
| New uploads remain stuck | The underlying Apple processing issue may still be active. Contact Apple Developer Support with the error details. |

If you report a problem in this repository, include the command used, your Python version, and the relevant error message. Remove private keys, authentication tokens, and personal information from anything you share.

## Scope and limitations

This is a community workaround that worked for the author’s affected app. It is not an Apple product or a guaranteed fix for every upload failure. Apple may reject API deletion requests, and removing a stuck set does not repair an ongoing processing outage.

The script operates on standard screenshot sets for one iOS App Store version and locale. It does not manage app preview videos, custom product pages, product page optimization experiments, or macOS app versions.

## References

- [App Store Connect API overview](https://developer.apple.com/help/app-store-connect/get-started/app-store-connect-api/)
- [Generating Tokens for API Requests](https://developer.apple.com/documentation/appstoreconnectapi/generating-tokens-for-api-requests)
- [Delete an App Screenshot Set](https://developer.apple.com/documentation/appstoreconnectapi/delete-v1-appscreenshotsets-_id_)

## Author

**Mohamad Masri** — independent iOS developer.

[View my App Store portfolio](https://apps.apple.com/developer/mohammad-masri/id975614455)

If this tool helped you unblock a release, consider starring the repository or sharing it with another developer experiencing the same issue.
