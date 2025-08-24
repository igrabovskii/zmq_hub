(function () {
  const statusEl = document.getElementById('status');
  const eventsEl = document.getElementById('events');
  const countTotalEl = document.getElementById('count-total');
  const countDroppedEl = document.getElementById('count-dropped');
  const pubForm = document.getElementById('pub-form');
  const topicEl = document.getElementById('topic');
  const payloadEl = document.getElementById('payload');
  const encodingEl = document.getElementById('encoding');
  const pubResultEl = document.getElementById('pub-result');

  let total = 0;
  let dropped = 0;

  function wsUrl(path) {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${location.host}${path}`;
  }

  let eventsWs;
  let controlWs;

  function connect() {
    eventsWs = new WebSocket(wsUrl('/ws/events'));
    eventsWs.onopen = () => {
      statusEl.textContent = 'Connected';
    };
    eventsWs.onclose = () => {
      statusEl.textContent = 'Disconnected, retrying…';
      setTimeout(connect, 1000);
    };
    eventsWs.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        total += 1;
        countTotalEl.textContent = String(total);
        const pre = document.createElement('pre');
        pre.textContent = JSON.stringify(data, null, 2);
        pre.className = `kind-${data.kind || 'unknown'}`;
        eventsEl.appendChild(pre);
        while (eventsEl.childNodes.length > 1000) {
          eventsEl.removeChild(eventsEl.firstChild);
        }
      } catch (e) {
        console.error('bad event', e);
      }
    };

    controlWs = new WebSocket(wsUrl('/ws/control'));
    controlWs.onopen = () => {
      console.log('control connected');
    };
    controlWs.onclose = () => {
      console.log('control disconnected');
    };
    controlWs.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.dropped_ws) {
          dropped = data.dropped_ws;
          countDroppedEl.textContent = String(dropped);
        }
        if (data.ok === false) {
          pubResultEl.textContent = 'Error: ' + (data.error || 'unknown');
        } else if (data.ok === true) {
          pubResultEl.textContent = 'Published';
          setTimeout(() => (pubResultEl.textContent = ''), 1000);
        }
      } catch (e) {}
    };
  }

  pubForm.addEventListener('submit', function (e) {
    e.preventDefault();
    const topic = topicEl.value.trim();
    const payload = payloadEl.value;
    const encoding = encodingEl.value;
    if (!topic) {
      pubResultEl.textContent = 'Topic required';
      return;
    }
    const msg = { action: 'publish', topic, payload, encoding };
    if (controlWs && controlWs.readyState === WebSocket.OPEN) {
      controlWs.send(JSON.stringify(msg));
    } else {
      pubResultEl.textContent = 'Control socket not connected';
    }
  });

  connect();
})();
