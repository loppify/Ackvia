async def test_setup_page_contains_authenticated_onboarding_flow(client):
    response = await client.get("/")

    assert response.status_code == 200

    html = response.text
    assert 'id="auth-card"' in html
    assert "onclick=\"authenticate('register')\"" in html
    assert "onclick=\"authenticate('login')\"" in html
    assert 'fetch("/api/workspaces"' in html
    assert "workspace_id: currentWorkspaceId" in html
