# Realtime ASL Translator MVP

This is a first-version realtime English ASL recognition pipeline:

1. Train an isolated-sign classifier on free landmark data.
2. Read webcam frames in realtime.
3. Extract MediaPipe landmarks.
4. Run a sliding-window model.
5. Smooth repeated window predictions into an English subtitle stream.

## Dataset

Recommended free dataset: **Google - Isolated Sign Language Recognition** on Kaggle.

Why this one:

- It is ASL / English-word oriented.
- It has about 100k isolated sign examples from a 250-sign vocabulary.
- It already provides MediaPipe landmarks, so the MVP can train without downloading raw videos.

Dataset page:

https://www.kaggle.com/competitions/asl-signs/data

The expected local structure after download/unzip is:

```text
data/asl-signs/
  train.csv
  sign_to_prediction_index_map.json
  train_landmark_files/
    ...
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Download the dataset with Kaggle CLI:

```powershell
kaggle competitions download -c asl-signs -p data/asl-signs
Expand-Archive data/asl-signs/asl-signs.zip -DestinationPath data/asl-signs
```

You need a Kaggle account and `kaggle.json` API token for the download command.

## Colab Disk-Saving Subset Extraction

The full Kaggle zip is large. For an MVP, do not unzip the whole archive. Download the zip, then extract only the selected parquet files:

```python
!mkdir -p data/asl-signs-zip data/asl-signs-mvp
!kaggle competitions download -c asl-signs -p data/asl-signs-zip
!python -m asl_realtime.prepare_subset \
  --zip data/asl-signs-zip/asl-signs.zip \
  --output-dir data/asl-signs-mvp \
  --max-classes 40 \
  --max-samples-per-class 120
```

Then train against the small extracted directory:

```python
!python -m asl_realtime.train \
  --data-dir data/asl-signs-mvp \
  --output-dir runs/asl_mvp \
  --epochs 10
```

After subset extraction succeeds, you may remove the large zip to free disk:

```python
!rm data/asl-signs-zip/asl-signs.zip
```

## Train A Small MVP Model

Start with a subset so you can verify the whole system quickly:

```powershell
python -m asl_realtime.train `
  --data-dir data/asl-signs `
  --output-dir runs/asl_mvp `
  --max-classes 40 `
  --max-samples-per-class 120 `
  --epochs 10
```

For a fuller run, remove `--max-classes` and increase samples/epochs.

## Realtime Webcam Demo

```powershell
python -m asl_realtime.realtime `
  --checkpoint runs/asl_mvp/best.pt `
  --labels runs/asl_mvp/labels.json
```

Controls:

- `q`: quit
- `c`: clear subtitle history

## What This MVP Does And Does Not Do

This version recognizes isolated ASL signs and stitches stable predictions into a simple English subtitle stream. It is not yet sentence-level ASL translation. The next upgrade is to train a continuous recognition model, usually gloss sequence first, then English sentence generation.
