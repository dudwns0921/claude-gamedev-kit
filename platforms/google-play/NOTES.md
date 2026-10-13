# Google Play

There is no upload command: `deploy.py` checks and builds, then says which file the user uploads in Play Console.

What the user does once. Claude does none of it for them.

- **Create the app** in Play Console (https://play.google.com/console — a developer account is needed). Its package name is the target:
  write `"target": "com.name.game"` in `deploy` in `kit.config.json`. It must equal the package name the build is made with, and it cannot change after the first upload.
- **Keep the upload key outside the repository, with a backup.** A bundle signed with another key is rejected. How the build is signed is in the engine's notes.
- **The version code must grow with every upload** — an upload with a code already used is rejected. How it is set is in the engine's notes.

Each upload, by the user: Play Console → the app → Test and release → a track (internal testing first) → Create new release → upload the bundle → review and roll out.
