import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Form, Submission, Workspace
from tests.conftest import create_form


@pytest.mark.asyncio
async def test_invalid_form_uuid(client: AsyncClient):
    random_id = uuid.uuid4()

    response = await client.post(
        f"/f/{random_id}",
        json={"dummy": "data"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_form_submissions_returns_only_its_submissions(
        db: AsyncSession,
        client: AsyncClient,
):
    form = await create_form(db, title="Test form")

    submission_1 = Submission(
        form=form,
        payload={"name": "Ivan"},
    )
    submission_2 = Submission(
        form=form,
        payload={"name": "Petro"},
    )

    db.add(form)
    await db.commit()

    response = await client.get(f"/api/forms/{form.id}/submissions")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert {item["id"] for item in data} == {
        submission_1.id,
        submission_2.id,
    }


@pytest.mark.asyncio
async def test_get_form_submissions_does_not_return_other_form_submissions(
        db: AsyncSession,
        client: AsyncClient,
):
    form_1 = await create_form(db, title="Form 1")
    form_2 = await create_form(db, title="Form 2")

    submission_1 = Submission(
        form=form_1,
        payload={"name": "Ivan"},
    )
    submission_2 = Submission(
        form=form_2,
        payload={"name": "Petro"},
    )

    db.add_all([form_1, form_2])
    await db.commit()

    response = await client.get(f"/api/forms/{form_1.id}/submissions")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == submission_1.id
    assert data[0]["id"] != submission_2.id


@pytest.mark.asyncio
async def test_get_form_submissions_are_ordered_newest_first(
        db: AsyncSession,
        client: AsyncClient,
):
    form = await create_form(db, title="Test form")

    old_submission = Submission(
        form=form,
        payload={"name": "Old"},
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    new_submission = Submission(
        form=form,
        payload={"name": "New"},
        created_at=datetime.now(timezone.utc),
    )

    db.add(form)
    await db.commit()

    response = await client.get(f"/api/forms/{form.id}/submissions")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["id"] == new_submission.id
    assert data[1]["id"] == old_submission.id


@pytest.mark.asyncio
async def test_get_form_submissions_respects_limit(
        db: AsyncSession,
        client: AsyncClient,
):
    form = await create_form(db, title="Test form")

    for i in range(5):
        Submission(
            form=form,
            payload={"number": i},
        )

    db.add(form)
    await db.commit()

    response = await client.get(
        f"/api/forms/{form.id}/submissions",
        params={"limit": 2},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_form_submissions_respects_offset(
        db: AsyncSession,
        client: AsyncClient,
):
    form = await create_form(db, title="Test form")

    now = datetime.now(timezone.utc)

    submissions = [
        Submission(
            form=form,
            payload={"number": i},
            created_at=now + timedelta(seconds=i),
        )
        for i in range(5)
    ]

    db.add(form)
    await db.commit()

    response = await client.get(
        f"/api/forms/{form.id}/submissions",
        params={
            "limit": 2,
            "offset": 2,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["id"] == submissions[2].id
    assert data[1]["id"] == submissions[1].id


@pytest.mark.asyncio
async def test_get_form_submissions_returns_404_for_unknown_form(
        client: AsyncClient,
):
    form_id = uuid.uuid4()

    response = await client.get(f"/api/forms/{form_id}/submissions")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_forms_returns_forms(
        db: AsyncSession,
        client: AsyncClient,
):
    form_1 = await create_form(db, title="Form 1")
    form_2 = await create_form(db, title="Form 2")

    db.add_all([form_1, form_2])
    await db.commit()

    response = await client.get("/api/forms")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert {item["id"] for item in data} == {
        str(form_1.id),
        str(form_2.id),
    }


@pytest.mark.asyncio
async def test_get_forms_are_ordered_newest_first(
        db: AsyncSession,
        client: AsyncClient,
):
    now = datetime.now(timezone.utc)

    old_form = await create_form(
        db,
        title="Old form",
        created_at=now - timedelta(hours=1),
    )
    new_form = await create_form(
        db,
        title="New form",
        created_at=now,
    )

    db.add_all([old_form, new_form])
    await db.commit()

    response = await client.get("/api/forms")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["id"] == str(new_form.id)
    assert data[1]["id"] == str(old_form.id)


@pytest.mark.asyncio
async def test_get_forms_respects_limit_and_offset(
        db: AsyncSession,
        client: AsyncClient,
):
    now = datetime.now(timezone.utc)

    forms = [
        await create_form(
            db,
            title=f"Form {i}",
            created_at=now + timedelta(seconds=i),
        )
        for i in range(5)
    ]

    db.add_all(forms)
    await db.commit()

    response = await client.get(
        "/api/forms",
        params={
            "limit": 2,
            "offset": 1,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["id"] == str(forms[3].id)
    assert data[1]["id"] == str(forms[2].id)


@pytest.mark.asyncio
async def test_get_forms_returns_empty_list_when_no_forms_exist(
        client: AsyncClient,
):
    response = await client.get("/api/forms")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_form_belongs_to_workspace(db: AsyncSession) -> None:
    form = await create_form(db, title="Contact Form")
    await db.commit()

    assert form.workspace_id == form.workspace.id


@pytest.mark.asyncio
async def test_workspace_contains_forms(db: AsyncSession) -> None:
    workspace = Workspace(name="Agency Workspace")
    first = Form(title="Contact Form", workspace=workspace)
    second = Form(title="Quote Form", workspace=workspace)
    db.add_all([first, second])
    await db.commit()

    await db.refresh(workspace, ["forms"])
    assert len(workspace.forms) == 2
    assert {form.title for form in workspace.forms} == {"Contact Form", "Quote Form"}


@pytest.mark.asyncio
async def test_form_cannot_exist_without_workspace(db: AsyncSession) -> None:
    from app.database.models import Form

    db.add(Form(title="Orphan Form"))
    with pytest.raises(Exception):
        await db.commit()
    await db.rollback()
