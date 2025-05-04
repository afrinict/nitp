// Main JavaScript file for NITP Abuja Chapter

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Handle form submissions
document.addEventListener('submit', function(e) {
    if (e.target.matches('form')) {
        const submitButton = e.target.querySelector('button[type="submit"]');
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
        }
    }
});

// Handle file upload previews
document.addEventListener('change', function(e) {
    if (e.target.matches('input[type="file"]')) {
        const fileInput = e.target;
        const preview = document.getElementById(fileInput.dataset.preview);
        if (preview && fileInput.files && fileInput.files[0]) {
            const reader = new FileReader();
            reader.onload = function(e) {
                preview.src = e.target.result;
            };
            reader.readAsDataURL(fileInput.files[0]);
        }
    }
});

// Handle socket.io connections
if (typeof io !== 'undefined') {
    const socket = io();
    
    socket.on('connect', function() {
        console.log('Connected to server');
    });
    
    socket.on('notification', function(data) {
        // Handle notifications
        console.log('Received notification:', data);
    });
} 