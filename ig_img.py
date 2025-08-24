import instaloader

L = instaloader.Instaloader()
post_url = "https://www.instagram.com/p/DNaFmHfPJqd/?img_index=1"
post = instaloader.Post.from_shortcode(L.context, post_url.split("/")[-2])

for i, url in enumerate(post.get_sidecar_nodes(), start=1):
    print("Downloading:", url.display_url)
    L.download_pic(f"image_{i}", url.display_url, post.date)
