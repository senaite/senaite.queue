Changelog
=========


1.0.4 (unreleased)
------------------

- #18 New `add_copy` function to add copies of existing tasks
- #17 Fix task splits are not being generated for generic actions
- #16 Preserve task properties when requeueing chunks of action tasks
- #15 Fix traceback on tasks for the reindex of objects security
- #14 Use initial task's default chunk size when creating subsequent tasks


1.0.3 (2021-07-24)
------------------

- #21 Improve the reindex security objects process
- Skip guard checks when current thread is a consumer
- Make the creation of WS with WST assignment more efficient
- Pin cryptography==3.1.1
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
