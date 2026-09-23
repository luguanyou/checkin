const categories = ['HOMEWORK', 'CLASSROOM', 'LAB', 'OTHER'];

function createScoreFixture(course, roster) {
  return {
    course: { id: course.id, name: course.name, status: course.status },
    class_group: { ...course.classes[0] },
    version: 0,
    readonly: false,
    rules_ready: false,
    settings: { base_score: '70', factors: Object.fromEntries(categories.map((key) => [key, null])) },
    items: [], records: [], summaries: [],
    students: roster.map((member) => ({
      enrollment_id: member.enrollment_id, student_id: member.student.id,
      student_number: member.student.student_number, student_name: member.student.name,
      enrollment_status: member.enrollment_status,
    })),
  };
}

// Deterministic responses for browser interaction checks; calculation correctness is
// covered by the backend tests against MySQL, not by this stub.
function scoreBookResponse(book) {
  book.rules_ready = book.settings.base_score !== null && categories.every((key) => book.settings.factors[key] !== null);
  book.summaries = book.students.map((student) => ({
    enrollment_id: student.enrollment_id,
    categories: categories.map((category) => ({ category, points: '0', contribution: book.rules_ready ? '0' : null, pending: 0 })),
    raw_score: book.rules_ready ? book.settings.base_score : null,
    final_score: book.rules_ready ? book.settings.base_score : null,
    status: book.rules_ready ? 'READY' : 'RULES_PENDING',
  }));
  return book;
}

async function handleScoreRequest({ route, endpoint, method, url, book, json, error }) {
  const prefix = `/api/v1/classes/${book.class_group.id}/scores`;
  if (!endpoint.startsWith(prefix)) return false;
  const suffix = endpoint.slice(prefix.length);
  if (method === 'GET') {
    if (!suffix) await json(scoreBookResponse(book));
    else if (suffix === '/history') await json({ items: [] });
    else if (suffix === '/export') {
      const format = url.searchParams.get('format');
      await route.fulfill({ status: 200, headers: {
        'Content-Type': format === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'Content-Disposition': `attachment; filename*=UTF-8''scores.${format}`,
      }, body: 'scores export fixture' });
    } else await error('NOT_FOUND', '成绩接口不存在', 404);
    return true;
  }
  const body = route.request().postDataJSON();
  if (body.expected_version !== book.version) {
    await error('SCORE_VERSION_CONFLICT', '成绩已被其他页面修改，请重新载入', 409);
    return true;
  }
  if (suffix === '/settings' && method === 'PUT') {
    book.settings = { base_score: body.base_score, factors: body.factors };
  } else if (suffix === '/items' && method === 'POST') {
    const { expected_version, ...item } = body;
    book.items.push({ ...item, id: `score-item-${book.items.length + 1}` });
  } else {
    const match = suffix.match(/^\/items\/([^/]+)(\/records)?$/);
    if (!match) { await error('NOT_FOUND', '成绩接口不存在', 404); return true; }
    if (match[2] && method === 'PUT') {
      for (const entry of body.records) {
        let record = book.records.find((item) => item.item_id === match[1] && item.enrollment_id === entry.enrollment_id);
        if (!record) {
          record = { id: `score-record-${book.records.length + 1}`, item_id: match[1] };
          book.records.push(record);
        }
        Object.assign(record, entry, { updated_at: '2026-09-22T09:00:00Z' });
      }
    } else if (method === 'PATCH') {
      const { expected_version, ...changes } = body;
      Object.assign(book.items.find((item) => item.id === match[1]), changes);
    } else { await error('NOT_FOUND', '成绩接口不存在', 404); return true; }
  }
  book.version += 1;
  await json(scoreBookResponse(book), suffix === '/items' && method === 'POST' ? 201 : 200);
  return true;
}

module.exports = { createScoreFixture, handleScoreRequest };
