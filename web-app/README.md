# SignLearn Coach Web App

React + Tailwind CSS frontend for an ASL learning education demo.

## Pages

- Home: today learning, progress cards, course entry
- Courses: letters, common words, daily scenes, AI practice
- Sign Detail: meaning, action steps, demo video area
- AI Practice: standard demo, camera view, realtime score and keypoint tips
- Progress: study days, accuracy, mastered vocabulary, review queue

## Run

```bash
npm install
npm run dev
```

Open the Vite URL shown in the terminal, usually:

```text
http://127.0.0.1:5173
```

Use `127.0.0.1` or `localhost` for camera access. Browsers treat local origins as trusted for `getUserMedia`. Do not open `http://0.0.0.0:5173`; Chrome may treat that as unsafe and block the camera.

If you need to test from another device on the same Wi-Fi, run:

```bash
npm run dev:lan
```

LAN/mobile testing usually requires HTTPS or a tunneling tool such as ngrok/Cloudflare Tunnel because browser camera permissions are blocked on plain HTTP network addresses.

## Notes

The camera preview uses browser `getUserMedia`. The AI Practice page sends camera frames to the local backend:

```text
http://127.0.0.1:8000/api/practice/frame
```

Start the backend from the workspace root before practicing:

```bash
python -m asl_realtime.api_server --checkpoint asl_realtime_mvp_colab_subset/runs/runs/asl_mvp/best.pt --labels asl_realtime_mvp_colab_subset/runs/runs/asl_mvp/labels.json
```
