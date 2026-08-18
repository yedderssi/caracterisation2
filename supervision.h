#ifndef SUPERVISION_H
#define SUPERVISION_H

#include <QDialog>

namespace Ui {
class supervision;
}

class supervision : public QDialog
{
    Q_OBJECT

public:
    explicit supervision(QWidget *parent = nullptr);
    ~supervision();

private:
    Ui::supervision *ui;
};

#endif // SUPERVISION_H
