/**
 * Cloudflare Worker for MYTV Mana-Mana Live Auto-Signing IPTV Proxy
 * Deploy this to Cloudflare Workers if you want clean URLs (e.g. https://your-worker.subdomain.workers.dev/live/tv1.m3u8)
 * that dynamically sign and redirect to active Tenbyte CDN streams on demand.
 */

const BASE_API = "https://co3y6iwoio.tenbytecdn.com/api/v1";

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
  'Origin': 'https://mana2.my',
  'Referer': 'https://mana2.my/',
  'Content-Type': 'application/json'
};

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === '/' || path === '/playlist.m3u8' || path === '/playlist.m3u') {
      // Return playlist pointing to this worker's dynamic clean channel endpoints
      const channelRes = await fetch(`${BASE_API}/public/channels`, { headers: HEADERS });
      const channelData = await channelRes.json();
      const channels = channelData.data || [];

      let m3u = '#EXTM3U x-tvg-url="https://raw.githubusercontent.com/kerklangsi/MYtvmana2/main/epg.xml.gz"\n';

      for (const ch of channels) {
        const slug = ch.slug || ch.id;
        const name = ch.name || 'Unknown';
        const logo = ch.logoUrl || ch.thumbnailUrl || '';
        const chno = ch.channelNumber || 0;
        const group = ch.channelType === 'radio' ? 'MYTV Radio' : 'MYTV Live';
        const streamUrl = `${url.origin}/stream/${slug}.m3u8`;

        m3u += `#EXTINF:-1 tvg-id="${slug}" tvg-name="${name}" tvg-logo="${logo}" tvg-chno="${chno}" group-title="${group}",${name}\n`;
        m3u += `${streamUrl}\n`;
      }

      return new Response(m3u, {
        headers: { 'Content-Type': 'application/x-mpegurl', 'Access-Control-Allow-Origin': '*' }
      });
    }

    if (path.startsWith('/stream/')) {
      const slug = path.replace('/stream/', '').replace('.m3u8', '');
      
      // Fetch channel list to map slug -> channel ID
      const channelRes = await fetch(`${BASE_API}/public/channels`, { headers: HEADERS });
      const channelData = await channelRes.json();
      const channels = channelData.data || [];
      const ch = channels.find(c => (c.slug === slug || c.id === slug));

      if (!ch) {
        return new Response('Channel not found', { status: 404 });
      }

      const deviceId = crypto.randomUUID();
      const playPayload = {
        channelId: ch.id,
        deviceId: deviceId,
        protocol: 'hls',
        context: { deviceType: 'web', app: 'mytv-web', appVersion: '0.1.0', os: 'Windows', network: 'wifi' }
      };

      const playRes = await fetch(`${BASE_API}/public/streaming/channel-play`, {
        method: 'POST',
        headers: HEADERS,
        body: JSON.stringify(playPayload)
      });
      const playData = await playRes.json();
      const playbackUrl = playData.data?.playbackUrl || playData.data?.playbackUrls?.hls;

      if (!playbackUrl) {
        return new Response('Playback URL not found', { status: 502 });
      }

      // Redirect client to playback URL
      return Response.redirect(playbackUrl, 302);
    }

    return new Response('MYTV Proxy Worker Active', { status: 200 });
  }
};
