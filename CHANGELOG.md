# Changelog

## Unreleased

- Added POST /questions/{id}/upvote: upvote a question once per browser (tracked in a cookie)
- Added GET /moderate (HTTP Basic, ADMIN_PASSWORD): moderators can mark questions answered (POST /moderate/questions/{id}/answered) or delete them (DELETE /moderate/questions/{id}); answered questions are greyed out and sorted last
- Added GET /export.md: download all questions as Markdown, sorted by votes, with author, vote count and answered status
