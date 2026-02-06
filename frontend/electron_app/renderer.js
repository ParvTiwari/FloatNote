const ws = new WebSocket("ws://localhost:8000/ws/stt");

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    console.log("Text:", data.text);
    console.log("Keywords:", data.keywords);
    console.log("Intent:", data.intent);

    document.getElementById("live-text").innerText += data.text + " ";
    document.getElementById("intent").innerText = data.intent;
};