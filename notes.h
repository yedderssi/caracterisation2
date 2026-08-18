#ifndef NOTES_H
#define NOTES_H

#include <QDialog>

namespace Ui {
class notes;
}

class notes : public QDialog
{
    Q_OBJECT

public:
    explicit notes(QWidget *parent = nullptr);
    ~notes();

private:
    Ui::notes *ui;
};

#endif // NOTES_H
