# Separately authorized references required

This code snapshot contains no ASL Citizen reference vectors, manifest, provenance
data, videos or checkpoints. It does not resolve dataset licensing.

Before starting the application, independently provide authorized `index.npz` and
`manifest.json` here (container path `/app/deploy/reference`). They must satisfy the
30-word, 187-vector, 22080-dimension runtime contract. Do not add them to Git or to
the Docker build context/image. Do not use a public download as a substitute for permission.

The [ASL Citizen research license](https://www.microsoft.com/en-us/research/project/asl-citizen/dataset-license/)
restricts use to non-commercial research and prohibits distributing the data or
modifications. Public deployment or redistribution requires appropriate authorization.
No terms are accepted by this repository or on the user's behalf.

The app deliberately fails startup if these files are missing; it has no synthetic
scoring fallback. SHA256 values must come from your separately trusted asset record.
Run the explicit check described in the root README before startup. Unit tests use
artificial data and do not verify your real references.
