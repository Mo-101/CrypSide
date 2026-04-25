export async function GET() {
  return new Response('WebSockets are not fully supported in this serverless environment mockup', {
    status: 426, // Upgrade Required / Mock WS failure
    headers: { 'Connection': 'close' },
  });
}
