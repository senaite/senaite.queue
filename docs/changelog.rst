Changelog
=========

1.0.3 (unreleased)
------------------

- Fix client's queue tasks in "queued" status are not updated when "running"


1.0.2 (2020-11-15)
------------------

- Support for multiple consumers (up to 4 concurrent processes)
- Added JSON API endpoints for both queue server and clients
- Queue server-client implementation, without the need of annotations
- Added PAS plugin for authentication, with symmetric encryption
- Delegate the reindex object security to queue when linking contacts to users
- #7 Allow to queue generic worflow actions without specific adapter
- #7 Redux and better performance
- #6 Allow the prioritization of tasks
- #5 No actions can be done to worksheets with queued jobs


1.0.1 (2020-02-09)
------------------

- Allow to manually assign the username to the task to be queued
- Support for failed tasks
- Notify when the value for max_seconds_unlock is too low
- #3 New `queue_tasks` view with the list of tasks and statistics
- #2 Add max_retries setting for failing tasks
- #1 Add sample guard to prevent transitions when queued analyses


1.0.0 (2019-11-10)
------------------

First version
