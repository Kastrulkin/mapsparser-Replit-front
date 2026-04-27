import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { BusinessSwitcher } from "@/components/BusinessSwitcher";
import {
  DashboardBusinessInfoSection,
  DashboardInviteSection,
  DashboardMapsToolsSection,
  DashboardProfileSection,
  DashboardTabContent,
  DashboardTabsShell,
  DashboardWelcomeSection,
} from "@/components/dashboard/DashboardSections";
import { useDashboardController } from "@/components/dashboard/useDashboardController";

const Dashboard = () => {
  const {
    user,
    loading,
    editMode,
    setEditMode,
    form,
    setForm,
    error,
    setError,
    success,
    setSuccess,
    inviteSuccess,
    setInviteSuccess,
    activeTab,
    setActiveTab,
    userServices,
    businesses,
    currentBusinessId,
    currentBusiness,
    currentNetworkId,
    currentLocationId,
    setCurrentLocationId,
    loadingServices,
    showAddService,
    setShowAddService,
    newService,
    setNewService,
    showTransactionForm,
    setShowTransactionForm,
    clientInfo,
    setClientInfo,
    editClientInfo,
    setEditClientInfo,
    savingClientInfo,
    refreshingMapsData,
    profileCompletion,
    connectedMapTypes,
    connectedMapLabels,
    handleBusinessChange,
    handleRefreshMapsData,
    addService,
    deleteService,
    handleSaveClientInfo,
    handleUpdateProfile,
    handleSignOut,
  } = useDashboardController();

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Загрузка...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Доступ запрещён</h1>
          <p className="text-gray-600 mb-6">Необходима авторизация</p>
          <Button onClick={() => window.location.href = '/login'}>
            Войти
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="fixed top-0 left-0 right-0 z-50 bg-white/70 backdrop-blur-md border-b border-gray-200/50 shadow-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-3xl font-bold text-gray-900">Личный кабинет</h1>
            <div className="flex items-center space-x-4 gap-2">
              {user.is_superadmin && businesses.length > 0 ? (
                <BusinessSwitcher
                  businesses={businesses}
                  currentBusinessId={currentBusinessId || undefined}
                  onBusinessChange={handleBusinessChange}
                  isSuperadmin={true}
                />
              ) : null}
              {user.is_superadmin && businesses.length === 0 ? (
                <div className="text-xs text-gray-500 px-2 py-1 bg-gray-100 rounded">
                  Загрузка бизнесов...
                </div>
              ) : null}
              <Button
                variant="outline"
                size="sm"
                onClick={handleSignOut}
              >
                Выйти
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8 pt-24">
        <DashboardWelcomeSection
          currentBusiness={currentBusiness}
          profileCompletion={profileCompletion}
        />

        {error ? (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        ) : null}

        {success ? (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mb-4">
            {success}
          </div>
        ) : null}

        <DashboardProfileSection
          form={form}
          editMode={editMode}
          onEdit={() => setEditMode(true)}
          onCancel={() => setEditMode(false)}
          onSave={handleUpdateProfile}
          onFormChange={setForm}
        />

        <DashboardBusinessInfoSection
          clientInfo={clientInfo}
          editClientInfo={editClientInfo}
          savingClientInfo={savingClientInfo}
          onEdit={() => setEditClientInfo(true)}
          onCancel={() => setEditClientInfo(false)}
          onSave={handleSaveClientInfo}
          onClientInfoChange={setClientInfo}
        />

        <DashboardTabsShell
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

        <div className="mb-6 bg-gradient-to-r from-gray-50 to-white rounded-lg border-2 border-gray-200 shadow-sm p-4">
          <div className="mt-6">
            <DashboardTabContent
              activeTab={activeTab}
              showTransactionForm={showTransactionForm}
              onToggleTransactionForm={() => setShowTransactionForm((value) => !value)}
              onTransactionSuccess={() => {
                setShowTransactionForm(false);
                setSuccess('Транзакция добавлена успешно!');
              }}
              onTransactionCancel={() => setShowTransactionForm(false)}
              currentNetworkId={currentNetworkId}
              currentBusinessId={currentBusinessId}
              currentLocationId={currentLocationId}
              onLocationChange={setCurrentLocationId}
              showAddService={showAddService}
              newService={newService}
              loadingServices={loadingServices}
              userServices={userServices}
              onShowAddService={() => setShowAddService(true)}
              onHideAddService={() => setShowAddService(false)}
              onNewServiceChange={setNewService}
              onAddService={addService}
              onDeleteService={deleteService}
            />
          </div>
        </div>

        <DashboardMapsToolsSection
          currentBusinessId={currentBusinessId}
          clientInfo={clientInfo}
          connectedMapTypes={connectedMapTypes}
          connectedMapLabels={connectedMapLabels}
          refreshingMapsData={refreshingMapsData}
          onRefreshMapsData={handleRefreshMapsData}
          userServices={userServices}
        />

        <DashboardInviteSection
          inviteSuccess={inviteSuccess}
          onSuccess={() => setInviteSuccess(true)}
          onError={setError}
        />
      </div>
      <Footer />
    </div>
  );
};

export default Dashboard;
