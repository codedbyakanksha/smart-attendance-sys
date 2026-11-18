
document.addEventListener("DOMContentLoaded", function () {

    const video = document.getElementById("enrollVideo");
    const canvas = document.getElementById("enrollCanvas");
    const imageInput = document.getElementById("faceImage");

    const startButton = document.getElementById("startEnroll");
    const captureButton = document.getElementById("captureEnroll");

    const status = document.getElementById("enrollStatus");
    const form = document.getElementById("studentForm");

    if (!video || !canvas || !startButton || !captureButton) {
        return;
    }

    let cameraStream = null;

    // Start camera
    startButton.addEventListener("click", async function () {

        try {

            if (!navigator.mediaDevices ||
                !navigator.mediaDevices.getUserMedia) {
                throw new Error("Camera is not supported by this browser.");
            }

            cameraStream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: "user",
                    width: { ideal: 640 },
                    height: { ideal: 480 }
                },
                audio: false
            });

            video.srcObject = cameraStream;

            await video.play();

            captureButton.disabled = false;

            status.textContent = "Camera started. Position one face in the frame.";

        } catch (error) {

            console.error("Camera Error:", error);

            status.textContent =
                "Camera access denied or camera is unavailable.";

        }

    });


    // Capture face image
    captureButton.addEventListener("click", function () {

        if (!cameraStream || video.readyState < 2) {
            status.textContent = "Please start the camera first.";
            return;
        }

        if (!video.videoWidth || !video.videoHeight) {
            status.textContent = "Camera is not ready. Try again.";
            return;
        }

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const context = canvas.getContext("2d");

        context.drawImage(
            video,
            0,
            0,
            canvas.width,
            canvas.height
        );

        const imageData = canvas.toDataURL("image/jpeg", 0.85);

        imageInput.value = imageData;

        status.textContent = "Face photo captured successfully!";

    });


    // Check before submitting
    form.addEventListener("submit", function (event) {

        if (imageInput.value) {

            const consent = form.querySelector(
                'input[name="consent"]'
            );

            if (!consent || !consent.checked) {
                event.preventDefault();
                status.textContent =
                    "Please obtain consent before face enrollment.";
                return;
            }

        }

    });


    // Stop camera when leaving the page
    window.addEventListener("beforeunload", function () {

        if (cameraStream) {
            cameraStream.getTracks().forEach(track => track.stop());
        }

    });

});
