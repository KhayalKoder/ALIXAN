import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined); // undefined=loading, null=guest, obj=user

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
      return data;
    } catch {
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setUser(data);
    return data;
  };

  const register = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    setUser(data);
    return data;
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch (e) { /* noop */ }
    setUser(null);
  };

  const updateAvatar = async (avatar_id) => {
    await api.patch("/auth/avatar", { avatar_id });
    setUser((u) => (u ? { ...u, avatar_id } : u));
  };

  return (
    <AuthContext.Provider value={{ user, setUser, login, register, logout, refresh, updateAvatar }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
