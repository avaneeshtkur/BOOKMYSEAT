/**
 * youtubeParser.js
 */

export function extractYouTubeVideoId(url) {
  if (!url || typeof url !== 'string') return null;

  const regex = /^[a-zA-Z0-9_-]{11}$/;

  try {
    const urlObj = new URL(url);
    if (urlObj.hostname === 'youtu.be') {
      const id = urlObj.pathname.slice(1).split('/')[0];
      return regex.test(id) ? id : null;
    }
    if (urlObj.hostname.includes('youtube.com')) {
      const v = urlObj.searchParams.get('v');
      if (v && regex.test(v)) return v;

      if (urlObj.pathname.startsWith('/embed/')) {
        const id = urlObj.pathname.split('/embed/')[1];
        return regex.test(id) ? id : null;
      }
    }
  } catch (e) {
    // If it's already an 11-char ID
    if (regex.test(url)) return url;
  }
  return null;
}

export function buildEmbedUrl(videoId) {
  if (!videoId || !/^[a-zA-Z0-9_-]{11}$/.test(videoId)) return null;
  return `https://www.youtube.com/embed/${videoId}?autoplay=1&mute=1&controls=1&rel=0`;
}
