# File transfer service

A small resumable upload service: multipart uploads for small files, chunked
`PATCH` uploads for large ones, plus webhooks, notifications and retention.

Run the tests from this directory:

```
python3 -m unittest discover -s tests -t .
```
