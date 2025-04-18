# SoNo Backend

## API Documentation

### Collaboration Requests

#### Creating Collaboration Requests
`POST /api/auth/collaboration-requests/`

**Parameters:**
- `receiver_id` (required): The ID of the user who will receive the collaboration request
- `receiver_type` (required): The type of user ('artist' or 'producer')
- `message` (required): The collaboration message

**Example Request:**
```json
{
  "receiver_id": 5,
  "receiver_type": "artist",
  "message": "I'd like to collaborate with you on a new track!"
}
```

**Example Response:**
```json
{
  "id": 1,
  "message": "I'd like to collaborate with you on a new track!",
  "status": "pending",
  "created_at": "2025-03-27T10:15:30Z",
  "updated_at": "2025-03-27T10:15:30Z",
  "sender_type": "producer",
  "receiver_type": "artist",
  "sender_details": { ... },
  "receiver_details": { ... }
}
```

#### Getting Collaboration Requests
`GET /api/auth/collaboration-requests/`

This endpoint returns three collections:
- `sent`: Requests sent by the authenticated user
- `received`: Requests received by the authenticated user
- `all`: All requests involving the authenticated user

**Example Response:**
```json
{
  "sent": [ ... ],
  "received": [ ... ],
  "all": [ ... ]
}
```

#### Accepting/Rejecting Requests
`POST /api/auth/collaboration-requests/{request_id}/action/`

**Parameters:**
- `action` (required): Either 'accept' or 'reject'

**Example Request:**
```json
{
  "action": "accept"
}
```

### Debugging Collaboration Requests

For troubleshooting, we've added a test endpoint that doesn't require authentication:

`GET /api/auth/test/collaboration-requests/`

This endpoint shows all collaboration requests in the system and their details.

`POST /api/auth/test/collaboration-requests/`

This endpoint allows creating test collaboration requests with the following parameters:
- `sender_id`: The ID of the sender
- `sender_type`: 'artist' or 'producer'
- `receiver_id`: The ID of the receiver
- `receiver_type`: 'artist' or 'producer'
- `message`: Collaboration message (optional)

## Recent Changes (March 2025)

1. Added support for any user type to send/receive collaboration requests
2. Updated parameter naming from `receiver` to `receiver_id` + `receiver_type`
3. Maintained backward compatibility for older clients
4. Added test endpoints for debugging collaboration request issues 