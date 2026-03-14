import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import Credentials from "next-auth/providers/credentials";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Google,
    Credentials({
      id: "admin-password",
      name: "Admin Password",
      credentials: {
        password: { label: "Password", type: "password" },
      },
      authorize(credentials) {
        const adminPassword = process.env.ADMIN_PASSWORD;
        if (!adminPassword) return null; // disabled if not set
        if (credentials?.password === adminPassword) {
          return { id: "admin", name: "Admin", email: "admin@local" };
        }
        return null;
      },
    }),
  ],
  pages: {
    signIn: "/login",
  },
  callbacks: {
    authorized({ auth: session, request }) {
      const isLoginPage = request.nextUrl.pathname === "/login";
      const isAuthenticated = !!session?.user;
      if (isLoginPage) return true;
      return isAuthenticated;
    },
    signIn({ user, account }) {
      // Credentials (admin) always allowed if authorize() returned a user
      if (account?.provider === "admin-password") return true;
      // Google: check email whitelist
      const allowedRaw = process.env.ALLOWED_EMAILS ?? "";
      if (!allowedRaw) return true;
      const allowed = allowedRaw.split(",").map((e) => e.trim().toLowerCase());
      return allowed.includes(user.email?.toLowerCase() ?? "");
    },
    session({ session }) {
      return session;
    },
  },
});
