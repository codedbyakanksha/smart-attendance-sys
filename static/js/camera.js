document.addEventListener("DOMContentLoaded", function () {

    function stopStream(stream) {
        if (stream) {
            stream.getTracks().forEach(function (track) {
                track.stop();
            });
        }
    }

    function setStatus(element, message, isError) {
        if (!element) {
            return;
        }

        element.textContent = message;
        element.classList.toggle("error", Boolean(isError));
    }

    async function startCamera(video, streamContainer, status) {
        if (!navigator.mediaDevices ||
            !navigator.mediaDevices.getUserMedia) {
            throw new Error(
                "Camera access requires a supported browser and a secure address such as localhost or HTTPS."
            );
        }

        stopStream(streamContainer.value);

        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: "user",
                width: { ideal: 1280 },
                height: { ideal: 720 }
            },
            audio: false
        });

        streamContainer.value = stream;
        video.srcObject = stream;
        await video.play();

        setStatus(status, "Camera started. Position one face in the frame.", false);
    }

    function cameraError(error) {
        console.error("Camera error:", error);

        if (error && error.name === "NotAllowedError") {
            return "Camera permission was denied. Allow camera access in the browser and try again.";
        }

        if (error && error.name === "NotFoundError") {
            return "No camera was found. Connect a camera and try again.";
        }

        if (error && error.name === "NotReadableError") {
            return "The camera is busy or unavailable. Close other apps using it and try again.";
        }

        return error && error.message
            ? error.message
            : "Could not start the camera. Please try again.";
    }

    function captureFrame(video, canvas) {
        if (!video.srcObject || video.readyState < 2) {
            return null;
        }

        if (!video.videoWidth || !video.videoHeight) {
            return null;
        }

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const context = canvas.getContext("2d");
        context.drawImage(video, 0, 0, canvas.width, canvas.height);

        return canvas.toDataURL("image/jpeg", 0.85);
    }

    const enrollVideo = document.getElementById("enrollVideo");
    const enrollCanvas = document.getElementById("enrollCanvas");
    const faceImage = document.getElementById("faceImage");
    const startEnroll = document.getElementById("startEnroll");
    const captureEnroll = document.getElementById("captureEnroll");
    const enrollStatus = document.getElementById("enrollStatus");
    const studentForm = document.getElementById("studentForm");

    if (enrollVideo && enrollCanvas && startEnroll && captureEnroll) {
        const enrollStream = { value: null };

        startEnroll.addEventListener("click", async function () {
            startEnroll.disabled = true;

            try {
                await startCamera(
                    enrollVideo,
                    enrollStream,
                    enrollStatus
                );
                captureEnroll.disabled = false;
            } catch (error) {
                setStatus(
                    enrollStatus,
                    cameraError(error),
                    true
                );
            } finally {
                startEnroll.disabled = false;
            }
        });

        captureEnroll.addEventListener("click", function () {
            const imageData = captureFrame(enrollVideo, enrollCanvas);

            if (!imageData) {
                setStatus(
                    enrollStatus,
                    "Camera is not ready. Wait a moment and try again.",
                    true
                );
                return;
            }

            faceImage.value = imageData;
            setStatus(
                enrollStatus,
                "Face photo captured successfully!",
                false
            );
        });

        if (studentForm) {
            studentForm.addEventListener("submit", function (event) {
                if (!faceImage || !faceImage.value) {
                    return;
                }

                const consent = studentForm.querySelector(
                    'input[name="consent"]'
                );

                if (!consent || !consent.checked) {
                    event.preventDefault();
                    setStatus(
                        enrollStatus,
                        "Please obtain consent before face enrollment.",
                        true
                    );
                }
            });
        }

        window.addEventListener("beforeunload", function () {
            stopStream(enrollStream.value);
        });
    }

    const scanVideo = document.getElementById("scanVideo");
    const scanCanvas = document.getElementById("scanCanvas");
    const startScan = document.getElementById("startScan");
    const scanNow = document.getElementById("scanNow");
    const stopScan = document.getElementById("stopScan");
    const scanStatus = document.getElementById("scanStatus");
    const cameraPlaceholder = document.getElementById("cameraPlaceholder");

    if (scanVideo && scanCanvas && startScan && scanNow && stopScan) {
        const scanStream = { value: null };

        function stopScanCamera() {
            stopStream(scanStream.value);
            scanStream.value = null;
            scanVideo.srcObject = null;
            scanNow.disabled = true;
            stopScan.disabled = true;

            if (cameraPlaceholder) {
                cameraPlaceholder.style.display = "";
            }

            setStatus(
                scanStatus,
                "Camera stopped.",
                false
            );
        }

        startScan.addEventListener("click", async function () {
            startScan.disabled = true;

            try {
                await startCamera(scanVideo, scanStream, scanStatus);

                scanNow.disabled = false;
                stopScan.disabled = false;

                if (cameraPlaceholder) {
                    cameraPlaceholder.style.display = "none";
                }
            } catch (error) {
                setStatus(
                    scanStatus,
                    cameraError(error),
                    true
                );
            } finally {
                startScan.disabled = false;
            }
        });

        stopScan.addEventListener("click", stopScanCamera);

        scanNow.addEventListener("click", async function () {
            const imageData = captureFrame(scanVideo, scanCanvas);

            if (!imageData) {
                setStatus(
                    scanStatus,
                    "Camera is not ready. Wait a moment and try again.",
                    true
                );
                return;
            }

            scanNow.disabled = true;
            setStatus(
                scanStatus,
                "Recognizing face...",
                false
            );

            try {
                const response = await fetch("/api/recognize", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ image: imageData })
                });

                const result = await response.json();

                setStatus(
                    scanStatus,
                    result.message ||
                        "Recognition request failed.",
                    !result.ok
                );
            } catch (error) {
                setStatus(
                    scanStatus,
                    "Could not contact the recognition service.",
                    true
                );
            } finally {
                if (scanStream.value) {
                    scanNow.disabled = false;
                }
            }
        });

        window.addEventListener("beforeunload", function () {
            stopStream(scanStream.value);
        });
    }

});
