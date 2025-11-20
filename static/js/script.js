document.addEventListener('DOMContentLoaded', function() {
    
    // --- DYNAMIC SIDEBAR ACTIVE LINK ---
    // This function finds the current page in the sidebar and highlights it.
    const setActiveSidebarLink = () => {
        const currentPath = window.location.pathname;
        const sidebarLinks = document.querySelectorAll('.sidebar nav a');
        
        sidebarLinks.forEach(link => {
            const linkPath = new URL(link.href).pathname;
            const listItem = link.parentElement;
            
            // Remove active class from all links first
            if (listItem.classList.contains('active')) {
                listItem.classList.remove('active');
            }
            
            // Add active class to the link that matches the current page URL
            if (currentPath === linkPath) {
                listItem.classList.add('active');
            }
        });
    };
    setActiveSidebarLink();


    // --- LOAN EMI CALCULATOR ---
    // This provides a real-time EMI estimate on the loan application page.
    const loanForm = document.querySelector('form[action="/user/apply_loan"]');
    if(loanForm) {
        const loanAmountInput = document.getElementById('loan_amount');
        const termMonthsInput = document.getElementById('term_months');
        const emiDisplay = document.getElementById('emi_display_amount');
        const interestRate = 8.0; // Annual interest rate in percent

        const calculateEMI = () => {
            const principal = parseFloat(loanAmountInput.value);
            const term = parseInt(termMonthsInput.value);
            
            if (principal > 0 && term > 0) {
                const monthlyRate = interestRate / 12 / 100;
                const emi = (principal * monthlyRate * Math.pow(1 + monthlyRate, term)) / (Math.pow(1 + monthlyRate, term) - 1);
                emiDisplay.textContent = `₹ ${emi.toFixed(2)}`;
            } else {
                emiDisplay.textContent = '₹ 0.00';
            }
        };

        [loanAmountInput, termMonthsInput].forEach(input => {
            input.addEventListener('keyup', calculateEMI);
            input.addEventListener('change', calculateEMI); // For number input arrows
        });
    }

    
    // --- CREATE ACCOUNT PAGE VALIDATION ---
    const createAccountForm = document.querySelector('form[action*="create_account"]');
    if (createAccountForm) {
        const password = document.getElementById('password');
        const confirmPassword = document.getElementById('confirm_password');
        const passwordError = document.getElementById('password-error');
        const pin = document.getElementById('pin');
        const confirmPin = document.getElementById('confirm_pin');
        const pinError = document.getElementById('pin-error');
        const phoneNumber = document.getElementById('phone_number');
        const phoneError = document.getElementById('phone-error');
        const submitButton = createAccountForm.querySelector('button[type="submit"]');

        const validateForm = () => {
            const passwordsMatch = password.value === confirmPassword.value;
            const pinsMatch = pin.value === confirmPin.value;
            const phoneIsValid = /^\d{10}$/.test(phoneNumber.value);

            // Password validation
            if (password.value && confirmPassword.value) {
                passwordError.textContent = passwordsMatch ? '' : 'Passwords do not match.';
            } else {
                passwordError.textContent = '';
            }

            // PIN validation
            if (pin.value && confirmPin.value) {
                pinError.textContent = pinsMatch ? '' : 'PINs do not match.';
            } else {
                 pinError.textContent = '';
            }
            
            // Phone number validation
            if (phoneNumber.value) {
                phoneError.textContent = phoneIsValid ? '' : 'Phone number must be 10 digits.';
            } else {
                phoneError.textContent = '';
            }
            
            // Disable submit button if validation fails
            submitButton.disabled = !(passwordsMatch && pinsMatch && phoneIsValid && pin.value.length === 4);
        };

        // Real-time input filtering for PIN to only allow numbers
        [pin, confirmPin].forEach(input => {
            input.addEventListener('input', () => {
                input.value = input.value.replace(/[^0-9]/g, '');
            });
        });

        [password, confirmPassword, pin, confirmPin, phoneNumber].forEach(input => {
            input.addEventListener('keyup', validateForm);
            input.addEventListener('blur', validateForm); // Validate when user leaves field
        });
    }


    // --- USER SETTINGS PAGE VALIDATION (EXISTING) ---
    const changePasswordForm = document.querySelector('#change-password-form');
    if (changePasswordForm) {
        const newPassword = document.getElementById('new_password');
        const confirmNewPassword = document.getElementById('confirm_new_password');
        const passwordError = document.getElementById('settings-password-error');
        const submitButton = changePasswordForm.querySelector('button[type="submit"]');

        const validatePasswordSettings = () => {
            const passwordsMatch = newPassword.value === confirmNewPassword.value;
            if(newPassword.value && confirmNewPassword.value){
                 passwordError.textContent = passwordsMatch ? '' : 'New passwords do not match.';
            } else {
                passwordError.textContent = '';
            }
            submitButton.disabled = !passwordsMatch || !newPassword.value;
        };
        [newPassword, confirmNewPassword].forEach(input => input.addEventListener('keyup', validatePasswordSettings));
    }
    
    const changePinForm = document.querySelector('#change-pin-form');
    if (changePinForm) {
        const newPin = document.getElementById('new_pin');
        const confirmNewPin = document.getElementById('confirm_new_pin');
        const pinError = document.getElementById('settings-pin-error');
        const submitButton = changePinForm.querySelector('button[type="submit"]');

        // Real-time input filtering for PIN to only allow numbers
        [newPin, confirmNewPin].forEach(input => {
            input.addEventListener('input', () => {
                input.value = input.value.replace(/[^0-9]/g, '');
            });
        });

        const validatePinSettings = () => {
            const pinsMatch = newPin.value === confirmNewPin.value;
            if(newPin.value && confirmNewPin.value) {
                pinError.textContent = pinsMatch ? '' : 'New PINs do not match.';
            } else {
                pinError.textContent = '';
            }
            submitButton.disabled = !pinsMatch || newPin.value.length !== 4;
        };
        [newPin, confirmNewPin].forEach(input => input.addEventListener('keyup', validatePinSettings));
    }

});

