(function () {
  const statusEl = document.getElementById('status');
  const eventsBody = document.getElementById('events-body');
  const countTotalEl = document.getElementById('count-total');
  const countDroppedEl = document.getElementById('count-dropped');
  const pubForm = document.getElementById('pub-form');
  const topicEl = document.getElementById('topic');
  const payloadEl = document.getElementById('payload');
  const encodingEl = document.getElementById('encoding');
  const pubResultEl = document.getElementById('pub-result');
  const clearBtn = document.getElementById('clear');

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

        const tr = document.createElement('tr');
        tr.className = `kind-${data.kind || 'unknown'}`;

        const tdTs = document.createElement('td');
        tdTs.textContent = data.ts || '';
        const tdKind = document.createElement('td');
        tdKind.textContent = data.kind || '';
        const tdSource = document.createElement('td');
        tdSource.textContent = data.source || '';
        const tdTopic = document.createElement('td');
        tdTopic.textContent = typeof data.topic === 'string' ? data.topic : (data.topic == null ? '' : String(data.topic));
        const tdPayload = document.createElement('td');
        const p = data.payload;
        tdPayload.textContent = Array.isArray(p) ? JSON.stringify(p) : (p == null ? '' : String(p));

        tr.appendChild(tdTs);
        tr.appendChild(tdKind);
        tr.appendChild(tdSource);
        tr.appendChild(tdTopic);
        tr.appendChild(tdPayload);

        eventsBody.insertBefore(tr, eventsBody.firstChild);
        while (eventsBody.childNodes.length > 1000) {
          eventsBody.removeChild(eventsBody.lastChild);
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

  clearBtn.addEventListener('click', function () {
    eventsBody.innerHTML = '';
  });

  connect();
})();
