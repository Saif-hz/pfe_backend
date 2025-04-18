import React, { useEffect } from 'react';
import axios from 'axios';

// This component demonstrates how to implement Google Sign-In
// You'll need to include the Google Identity script in your HTML:
// <script src="https://accounts.google.com/gsi/client"></script>

const GoogleSignIn = ({ onSuccess, onError }) => {
  useEffect(() => {
    // Load the Google Identity script
    const loadGoogleScript = () => {
      if (document.getElementById('google-identity-script')) return;
      
      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.id = 'google-identity-script';
      script.async = true;
      script.defer = true;
      document.body.appendChild(script);
      
      script.onload = initializeGoogleButton;
    };

    const initializeGoogleButton = () => {
      if (!window.google) return;
      
      window.google.accounts.id.initialize({
        client_id: '512283829471-nos129p3poia3256spjjr4l59u6jcs7k.apps.googleusercontent.com',
        callback: handleGoogleResponse,
        auto_select: false,
        cancel_on_tap_outside: true,
      });
      
      window.google.accounts.id.renderButton(
        document.getElementById('googleSignInDiv'),
        { theme: 'outline', size: 'large', width: 250, text: 'signin_with' }
      );
    };

    loadGoogleScript();
    
    return () => {
      // Cleanup
      const script = document.getElementById('google-identity-script');
      if (script) script.remove();
    };
  }, []);

  const handleGoogleResponse = async (response) => {
    try {
      // Send the ID token to your backend
      const result = await axios.post('/api/auth/google-login/', {
        id_token: response.credential
      });
      
      if (result.data && result.data.tokens) {
        // Store tokens in localStorage or your preferred state management
        localStorage.setItem('accessToken', result.data.tokens.access);
        localStorage.setItem('refreshToken', result.data.tokens.refresh);
        
        // Call the success callback with user data
        if (onSuccess) onSuccess(result.data.user);
      }
    } catch (error) {
      console.error('Google sign-in error:', error);
      if (onError) onError(error);
    }
  };

  return (
    <div>
      <div id="googleSignInDiv"></div>
    </div>
  );
};

export default GoogleSignIn;

// Usage example:
// 
// import GoogleSignIn from './GoogleSignIn';
// 
// function LoginPage() {
//   const handleLoginSuccess = (userData) => {
//     console.log('Logged in user:', userData);
//     // Redirect to dashboard or home page
//   };
//
//   const handleLoginError = (error) => {
//     console.error('Login failed:', error);
//     // Show error message to user
//   };
//
//   return (
//     <div className="login-page">
//       <h1>Login to Your Account</h1>
//       
//       {/* Your regular login form */}
//       
//       <div className="social-login">
//         <p>Or sign in with:</p>
//         <GoogleSignIn 
//           onSuccess={handleLoginSuccess} 
//           onError={handleLoginError} 
//         />
//       </div>
//     </div>
//   );
// } 