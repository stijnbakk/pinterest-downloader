# Pinterest Downloader

Simple Pinterest image downloader, that I use in combination with an Apple Shortcut to bookmark Pinterest images to Obsidian. Can be used as a standalone service. Running at `https://pinterest-downloader.fly.dev/scrape`

## Request

To use, provide a simple (expanded) pinterest URL in the request body. It will return a downloadable image.

```
POST https://pinterest-downloader.fly.dev/scrape/scrape
Content-Type: application/json

{
    "url": "https://pinterest.com/pin/123456789/"
}
```

## Example usage

```bash
curl -X POST -H "Content-Type: application/json" -d '{"url": "https://pinterest.com/pin/123456789/"}' http://localhost:8080/scrape
```

## To use in Apple Shortcuts

[Example shortcut](https://www.icloud.com/shortcuts/a7ed940b1cbc44deaf249a70462cfb70)

1. Receive URL from share sheet
2. Expand the URL (necessary because Pinterest by default gives a shortened URL)
3. Get contents of `https://pinterest-downloader.fly.dev/scrape` with
   - Headers: `Content-Type: application/json`
   - Body: `{"url": "expanded url"}`
4. Save file
