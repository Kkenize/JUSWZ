// Dashboard Functionality
document.addEventListener('DOMContentLoaded', function() {
    // Toggle active class on nav links
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            navLinks.forEach(l => l.classList.remove('active'));
            this.classList.add('active');
        });
        
        // Set active link based on current URL
        if (link.href === window.location.href) {
            link.classList.add('active');
        }
    });

    // Mobile responsiveness
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
        });
    }
});