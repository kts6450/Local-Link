import { Navigate, Route, Routes } from "react-router-dom";

import { RequireAuth } from "./components/RequireAuth";
import { RequireRole } from "./components/RequireRole";
import { ConsumerLayout } from "./layouts/ConsumerLayout";
import { SellerLayout } from "./layouts/SellerLayout";
import { CheckoutPage } from "./pages/CheckoutPage";
import { ListingDetailPage } from "./pages/ListingDetailPage";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { ShopPage } from "./pages/ShopPage";
import { AdminPage } from "./pages/admin/AdminPage";
import { SellerDashboardPage } from "./pages/seller/SellerDashboardPage";
import { SellerOrdersPage } from "./pages/seller/SellerOrdersPage";
import { SellerProductsPage } from "./pages/seller/SellerProductsPage";
import { SellerSnsPage } from "./pages/seller/SellerSnsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />

      <Route element={<RequireAuth />}>
      <Route element={<ConsumerLayout />}>
        <Route index element={<ShopPage />} />
        <Route path="listing/:id" element={<ListingDetailPage />} />
        <Route
          path="checkout"
          element={
            <RequireRole role="consumer">
              <CheckoutPage />
            </RequireRole>
          }
        />
      </Route>

      <Route path="seller" element={<SellerLayout />}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<SellerDashboardPage />} />
        <Route path="products" element={<SellerProductsPage />} />
        <Route path="sns" element={<SellerSnsPage />} />
        <Route path="orders" element={<SellerOrdersPage />} />
      </Route>

      <Route path="admin" element={<AdminPage />} />

      <Route path="supplier" element={<Navigate to="/seller/products" replace />} />
      <Route path="supplier/*" element={<Navigate to="/seller/products" replace />} />
      </Route>
    </Routes>
  );
}
