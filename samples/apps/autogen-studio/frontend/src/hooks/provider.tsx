import React, { useEffect, useState } from "react";
import {
  eraseCookie,
  fetchJSON,
  getLocalStorage,
  getServerUrl,
  setLocalStorage,
} from "../components/utils";
import { message } from "antd";

export interface IUser {
  name: string;
  email?: string;
  username?: string;
  avatar_url?: string;
  metadata?: any;
}

export interface AppContextType {
  user: IUser | null;
  setUser: any;
  logout: any;
  cookie_name: string;
  darkMode: string;
  setDarkMode: any;
}

const cookie_name = "coral_app_cookie_";

export const appContext = React.createContext<AppContextType>(
  {} as AppContextType
);
const Provider = ({ children }: any) => {
  const storedValue = getLocalStorage("darkmode", false);
  const [darkMode, setDarkMode] = useState(
    storedValue === null ? "light" : storedValue === "dark" ? "dark" : "light"
  );

  const logout = () => {
    setUser(null);
    // eraseCookie(cookie_name);
    let localHref = window.location.href;
    let ucDomain = localHref.indexOf('test') > 0 || localHref.indexOf('localhost') > 0 || localHref.indexOf('127.0.0.1') > 0 ? 'id.test.seewo.com' : 'id.seewo.com';
    const currentUrl = encodeURIComponent(localHref);
    window.location.href = `${window.location.protocol}//${ucDomain}/logoutToRedirect?redirect_url=${currentUrl}`;
  };

  const updateDarkMode = (darkMode: string) => {
    setDarkMode(darkMode);
    setLocalStorage("darkmode", darkMode, false);
  };

  // Modify logic here to add your own authentication
  const [user, setUser] = useState<IUser | null>(null);

  // add by ymc: fetch user
  const serverUrl = getServerUrl();
  const currentUserUrl = `${serverUrl}/current-user`;
  const fetchCurrentUser = () => {    
    const payLoad = {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    };
    const onSuccess = (data: any) => {
      setUser({
        name: data.real_name,
        email: data.user_id,
        username: data.user_name,
      });
    };
    const onError = (err: any) => {
      message.error(err.message);
    };
    fetchJSON(currentUserUrl, payLoad, onSuccess, onError);
  };
  useEffect(() => {
    fetchCurrentUser()
  }, []);
  
  return (
    <appContext.Provider
      value={{
        user,
        setUser,
        logout,
        cookie_name,
        darkMode,
        setDarkMode: updateDarkMode,
      }}
    >
      {children}
    </appContext.Provider>
  );
};

export default ({ element }: any) => <Provider>{element}</Provider>;
