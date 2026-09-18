// =========================================================
// FILL THESE TWO IN before using the app.
// Get them from: Supabase dashboard -> Settings -> API Keys
// Use the PUBLISHABLE key here (sb_publishable_...), NOT the secret key.
// The publishable key is safe to expose in browser code.
// =========================================================
const SUPABASE_URL = "https://yworpibfejlemnwctper.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "sb_secret_rDccaB2uOJMxd4WsDPk4lA_JxjLC5cm";

const supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);

// Redirects to login.html if nobody is signed in.
// Call this at the top of any page that requires login. Returns the user object if signed in.
async function requireAuth() {
  const { data: { session } } = await supabaseClient.auth.getSession();
  if (!session) {
    window.location.href = "login.html";
    return null;
  }
  return session.user;
}

async function logout() {
  await supabaseClient.auth.signOut();
  window.location.href = "login.html";
}

function displayName(user) {
  if (!user) return "Guest";
  return user.user_metadata?.full_name || user.email || "Guest";
}